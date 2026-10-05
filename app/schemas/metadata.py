from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _strip(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class ColumnSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    nullable: bool = True

    @field_validator("name", "type")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return _strip(value)

    @field_validator("description")
    @classmethod
    def strip_optional(cls, value: str) -> str:
        return value.strip()


class MetadataWrite(BaseModel):
    table_name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    database: str = Field(..., min_length=1, max_length=255)
    schema_name: str = Field(..., alias="schema", min_length=1, max_length=255)
    owner: str = Field(..., min_length=1, max_length=255)
    domain: str = Field(..., min_length=1, max_length=255)
    columns: list[ColumnSchema] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("table_name", "database", "schema_name", "owner", "domain")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return _strip(value)

    @field_validator("description")
    @classmethod
    def strip_optional(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def unique_column_names(self) -> "MetadataWrite":
        names = [column.name.lower() for column in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("column names must be unique within a table")
        return self


class MetadataResponse(BaseModel):
    id: str
    table_name: str
    description: str
    database: str
    schema_name: str = Field(..., serialization_alias="schema")
    owner: str
    domain: str
    columns: list[ColumnSchema]
    schema_version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class MetadataListResponse(BaseModel):
    items: list[MetadataResponse]
    total: int
    page: int
    page_size: int


class SchemaSnapshotResponse(BaseModel):
    schema_version: int
    columns: list[ColumnSchema]
    recorded_at: datetime


class SchemaHistoryResponse(BaseModel):
    metadata_id: str
    items: list[SchemaSnapshotResponse]
