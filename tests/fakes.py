from bson import ObjectId

from app.core.exceptions import ConflictError, InvalidIdError, NotFoundError
from app.models.metadata import Metadata, SchemaSnapshot


class InMemoryMetadataRepository:
    def __init__(self) -> None:
        self._items: dict[str, Metadata] = {}
        self._history: list[SchemaSnapshot] = []

    async def create(self, entity: Metadata) -> Metadata:
        if self._find_by_identity(*entity.identity_key()) is not None:
            raise ConflictError(
                "Metadata already exists for this database, schema and table"
            )
        entity.id = str(ObjectId())
        self._items[entity.id] = entity
        return entity

    async def get_by_id(self, metadata_id: str) -> Metadata:
        self._assert_valid_id(metadata_id)
        entity = self._items.get(metadata_id)
        if entity is None:
            raise NotFoundError("Metadata not found")
        return entity

    async def get_by_identity(
        self, database: str, schema_name: str, table_name: str
    ) -> Metadata | None:
        return self._find_by_identity(database, schema_name, table_name)

    async def list_metadata(
        self,
        *,
        table_name: str | None,
        owner: str | None,
        domain: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[Metadata], int]:
        items = list(self._items.values())
        if table_name:
            needle = table_name.lower()
            items = [item for item in items if needle in item.table_name.lower()]
        if owner:
            items = [item for item in items if item.owner.lower() == owner.lower()]
        if domain:
            items = [item for item in items if item.domain.lower() == domain.lower()]

        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[skip : skip + limit], len(items)

    async def update(self, entity: Metadata) -> Metadata:
        if entity.id is None:
            raise InvalidIdError("Metadata id is required")
        self._assert_valid_id(entity.id)
        if entity.id not in self._items:
            raise NotFoundError("Metadata not found")

        conflict = self._find_by_identity(*entity.identity_key())
        if conflict is not None and conflict.id != entity.id:
            raise ConflictError(
                "Metadata already exists for this database, schema and table"
            )

        self._items[entity.id] = entity
        return entity

    async def delete(self, metadata_id: str) -> None:
        self._assert_valid_id(metadata_id)
        if metadata_id not in self._items:
            raise NotFoundError("Metadata not found")
        del self._items[metadata_id]
        self._history = [
            snapshot for snapshot in self._history if snapshot.metadata_id != metadata_id
        ]

    async def add_snapshot(self, snapshot: SchemaSnapshot) -> SchemaSnapshot:
        snapshot.id = str(ObjectId())
        self._history.append(snapshot)
        return snapshot

    async def list_history(self, metadata_id: str) -> list[SchemaSnapshot]:
        self._assert_valid_id(metadata_id)
        return sorted(
            [snapshot for snapshot in self._history if snapshot.metadata_id == metadata_id],
            key=lambda snapshot: snapshot.schema_version,
        )

    def _find_by_identity(
        self, database: str, schema_name: str, table_name: str
    ) -> Metadata | None:
        for entity in self._items.values():
            if entity.identity_key() == (database, schema_name, table_name):
                return entity
        return None

    def _assert_valid_id(self, metadata_id: str) -> None:
        if not ObjectId.is_valid(metadata_id):
            raise InvalidIdError("Invalid metadata id")
