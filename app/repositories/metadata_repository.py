import re
from dataclasses import asdict
from typing import Protocol

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.core.exceptions import ConflictError, DatabaseError, InvalidIdError, NotFoundError
from app.models.metadata import Column, Metadata, SchemaSnapshot


class MetadataRepositoryPort(Protocol):
    async def create(self, entity: Metadata) -> Metadata: ...
    async def get_by_id(self, metadata_id: str) -> Metadata: ...
    async def get_by_identity(
        self, database: str, schema_name: str, table_name: str
    ) -> Metadata | None: ...
    async def list_metadata(
        self,
        *,
        table_name: str | None,
        owner: str | None,
        domain: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[Metadata], int]: ...
    async def update(self, entity: Metadata) -> Metadata: ...
    async def delete(self, metadata_id: str) -> None: ...
    async def add_snapshot(self, snapshot: SchemaSnapshot) -> SchemaSnapshot: ...
    async def list_history(self, metadata_id: str) -> list[SchemaSnapshot]: ...


class MetadataRepository:
    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._collection = database["metadata"]
        self._history = database["metadata_history"]

    async def create(self, entity: Metadata) -> Metadata:
        try:
            result = await self._collection.insert_one(self._to_document(entity))
        except DuplicateKeyError as exc:
            raise ConflictError(
                "Metadata already exists for this database, schema and table"
            ) from exc
        except PyMongoError as exc:
            raise DatabaseError("Failed to persist metadata") from exc

        entity.id = str(result.inserted_id)
        return entity

    async def get_by_id(self, metadata_id: str) -> Metadata:
        document = await self._safe_find_one({"_id": self._parse_id(metadata_id)})
        if document is None:
            raise NotFoundError("Metadata not found")
        return self._to_domain(document)

    async def get_by_identity(
        self, database: str, schema_name: str, table_name: str
    ) -> Metadata | None:
        document = await self._safe_find_one(
            {
                "database": database,
                "schema": schema_name,
                "table_name": table_name,
            }
        )
        return self._to_domain(document) if document else None

    async def list_metadata(
        self,
        *,
        table_name: str | None,
        owner: str | None,
        domain: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[Metadata], int]:
        query: dict = {}
        if table_name:
            query["table_name"] = {"$regex": re.escape(table_name), "$options": "i"}
        if owner:
            query["owner"] = {"$regex": f"^{re.escape(owner)}$", "$options": "i"}
        if domain:
            query["domain"] = {"$regex": f"^{re.escape(domain)}$", "$options": "i"}

        try:
            total = await self._collection.count_documents(query)
            cursor = (
                self._collection.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            documents = await cursor.to_list(length=limit)
        except PyMongoError as exc:
            raise DatabaseError("Failed to list metadata") from exc

        return [self._to_domain(document) for document in documents], total

    async def update(self, entity: Metadata) -> Metadata:
        if entity.id is None:
            raise InvalidIdError("Metadata id is required")

        try:
            result = await self._collection.replace_one(
                {"_id": self._parse_id(entity.id)},
                self._to_document(entity),
            )
        except DuplicateKeyError as exc:
            raise ConflictError(
                "Metadata already exists for this database, schema and table"
            ) from exc
        except PyMongoError as exc:
            raise DatabaseError("Failed to update metadata") from exc

        if result.matched_count == 0:
            raise NotFoundError("Metadata not found")
        return entity

    async def delete(self, metadata_id: str) -> None:
        object_id = self._parse_id(metadata_id)
        try:
            result = await self._collection.delete_one({"_id": object_id})
            if result.deleted_count == 0:
                raise NotFoundError("Metadata not found")
            await self._history.delete_many({"metadata_id": metadata_id})
        except NotFoundError:
            raise
        except PyMongoError as exc:
            raise DatabaseError("Failed to delete metadata") from exc

    async def add_snapshot(self, snapshot: SchemaSnapshot) -> SchemaSnapshot:
        try:
            result = await self._history.insert_one(self._snapshot_to_document(snapshot))
        except PyMongoError as exc:
            raise DatabaseError("Failed to persist schema history") from exc
        snapshot.id = str(result.inserted_id)
        return snapshot

    async def list_history(self, metadata_id: str) -> list[SchemaSnapshot]:
        self._parse_id(metadata_id)
        try:
            cursor = self._history.find({"metadata_id": metadata_id}).sort(
                "schema_version", 1
            )
            documents = await cursor.to_list(length=None)
        except PyMongoError as exc:
            raise DatabaseError("Failed to list schema history") from exc
        return [self._snapshot_to_domain(document) for document in documents]

    async def _safe_find_one(self, query: dict) -> dict | None:
        try:
            return await self._collection.find_one(query)
        except PyMongoError as exc:
            raise DatabaseError("Failed to query metadata") from exc

    def _parse_id(self, metadata_id: str) -> ObjectId:
        try:
            return ObjectId(metadata_id)
        except (InvalidId, TypeError) as exc:
            raise InvalidIdError("Invalid metadata id") from exc

    def _to_document(self, entity: Metadata) -> dict:
        return {
            "table_name": entity.table_name,
            "description": entity.description,
            "database": entity.database,
            "schema": entity.schema_name,
            "owner": entity.owner,
            "domain": entity.domain,
            "columns": [asdict(column) for column in entity.columns],
            "schema_version": entity.schema_version,
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
        }

    def _snapshot_to_document(self, snapshot: SchemaSnapshot) -> dict:
        return {
            "metadata_id": snapshot.metadata_id,
            "schema_version": snapshot.schema_version,
            "columns": [asdict(column) for column in snapshot.columns],
            "recorded_at": snapshot.recorded_at,
        }

    def _snapshot_to_domain(self, document: dict) -> SchemaSnapshot:
        return SchemaSnapshot(
            id=str(document["_id"]),
            metadata_id=document["metadata_id"],
            schema_version=document["schema_version"],
            columns=[Column(**column) for column in document["columns"]],
            recorded_at=document["recorded_at"],
        )

    def _to_domain(self, document: dict) -> Metadata:
        return Metadata(
            id=str(document["_id"]),
            table_name=document["table_name"],
            description=document["description"],
            database=document["database"],
            schema_name=document["schema"],
            owner=document["owner"],
            domain=document["domain"],
            columns=[Column(**column) for column in document["columns"]],
            schema_version=document["schema_version"],
            created_at=document["created_at"],
            updated_at=document["updated_at"],
        )
