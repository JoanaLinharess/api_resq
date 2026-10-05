from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Column:
    name: str
    type: str
    description: str
    nullable: bool

    def structure_key(self) -> tuple[str, str, bool]:
        return (self.name.lower(), self.type.lower(), self.nullable)


@dataclass
class Metadata:
    table_name: str
    description: str
    database: str
    schema_name: str
    owner: str
    domain: str
    columns: list[Column]
    id: str | None = None
    schema_version: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @classmethod
    def new(
        cls,
        *,
        table_name: str,
        description: str,
        database: str,
        schema_name: str,
        owner: str,
        domain: str,
        columns: list[Column],
    ) -> Metadata:
        now = utc_now()
        return cls(
            table_name=table_name,
            description=description,
            database=database,
            schema_name=schema_name,
            owner=owner,
            domain=domain,
            columns=columns,
            schema_version=1,
            created_at=now,
            updated_at=now,
        )

    def to_snapshot(self) -> SchemaSnapshot:
        if self.id is None:
            raise ValueError("Cannot snapshot metadata without an id")
        return SchemaSnapshot(
            metadata_id=self.id,
            schema_version=self.schema_version,
            columns=list(self.columns),
            recorded_at=utc_now(),
        )

    def apply_update(
        self,
        *,
        table_name: str,
        description: str,
        database: str,
        schema_name: str,
        owner: str,
        domain: str,
        columns: list[Column],
    ) -> bool:
        bumped = self.has_structural_change(columns)
        if bumped:
            self.schema_version += 1

        self.table_name = table_name
        self.description = description
        self.database = database
        self.schema_name = schema_name
        self.owner = owner
        self.domain = domain
        self.columns = columns
        self.updated_at = utc_now()
        return bumped

    def has_structural_change(self, columns: list[Column]) -> bool:
        current = {column.structure_key() for column in self.columns}
        incoming = {column.structure_key() for column in columns}
        return current != incoming

    def identity_key(self) -> tuple[str, str, str]:
        return (self.database, self.schema_name, self.table_name)


@dataclass
class SchemaSnapshot:
    metadata_id: str
    schema_version: int
    columns: list[Column]
    recorded_at: datetime
    id: str | None = None
