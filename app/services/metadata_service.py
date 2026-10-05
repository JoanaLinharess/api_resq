from dataclasses import dataclass

from app.core.exceptions import ConflictError
from app.models.metadata import Column, Metadata, SchemaSnapshot
from app.repositories.metadata_repository import MetadataRepositoryPort
from app.schemas.metadata import MetadataWrite


@dataclass(frozen=True)
class PaginatedMetadata:
    items: list[Metadata]
    total: int
    page: int
    page_size: int


class MetadataService:
    def __init__(self, repository: MetadataRepositoryPort) -> None:
        self._repository = repository

    async def create(self, payload: MetadataWrite) -> Metadata:
        await self._ensure_unique_identity(
            payload.database, payload.schema_name, payload.table_name
        )
        entity = Metadata.new(
            table_name=payload.table_name,
            description=payload.description,
            database=payload.database,
            schema_name=payload.schema_name,
            owner=payload.owner,
            domain=payload.domain,
            columns=self._to_columns(payload),
        )
        created = await self._repository.create(entity)
        await self._repository.add_snapshot(created.to_snapshot())
        return created

    async def get_by_id(self, metadata_id: str) -> Metadata:
        return await self._repository.get_by_id(metadata_id)

    async def list_metadata(
        self,
        *,
        table_name: str | None = None,
        owner: str | None = None,
        domain: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedMetadata:
        items, total = await self._repository.list_metadata(
            table_name=table_name,
            owner=owner,
            domain=domain,
            skip=(page - 1) * page_size,
            limit=page_size,
        )
        return PaginatedMetadata(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(self, metadata_id: str, payload: MetadataWrite) -> Metadata:
        entity = await self._repository.get_by_id(metadata_id)
        await self._ensure_unique_identity(
            payload.database,
            payload.schema_name,
            payload.table_name,
            exclude_id=entity.id,
        )
        bumped = entity.apply_update(
            table_name=payload.table_name,
            description=payload.description,
            database=payload.database,
            schema_name=payload.schema_name,
            owner=payload.owner,
            domain=payload.domain,
            columns=self._to_columns(payload),
        )
        updated = await self._repository.update(entity)
        if bumped:
            await self._repository.add_snapshot(updated.to_snapshot())
        return updated

    async def get_history(self, metadata_id: str) -> list[SchemaSnapshot]:
        await self._repository.get_by_id(metadata_id)
        return await self._repository.list_history(metadata_id)

    async def delete(self, metadata_id: str) -> None:
        await self._repository.delete(metadata_id)

    async def _ensure_unique_identity(
        self,
        database: str,
        schema_name: str,
        table_name: str,
        exclude_id: str | None = None,
    ) -> None:
        existing = await self._repository.get_by_identity(
            database, schema_name, table_name
        )
        if existing is not None and existing.id != exclude_id:
            raise ConflictError(
                "Metadata already exists for this database, schema and table"
            )

    def _to_columns(self, payload: MetadataWrite) -> list[Column]:
        return [
            Column(
                name=column.name,
                type=column.type,
                description=column.description,
                nullable=column.nullable,
            )
            for column in payload.columns
        ]
