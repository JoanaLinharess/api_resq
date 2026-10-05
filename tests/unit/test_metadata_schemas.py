import pytest
from pydantic import ValidationError

from app.schemas.metadata import MetadataWrite
from tests.conftest import sample_payload


def test_valid_payload() -> None:
    model = MetadataWrite.model_validate(sample_payload())
    assert model.schema_name == "public"
    assert model.table_name == "orders"
    assert len(model.columns) == 2


def test_blank_table_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MetadataWrite.model_validate(sample_payload(table_name="   "))


def test_duplicate_column_names_are_rejected() -> None:
    payload = sample_payload(
        columns=[
            {"name": "id", "type": "string", "description": "", "nullable": False},
            {"name": "ID", "type": "int", "description": "", "nullable": True},
        ]
    )
    with pytest.raises(ValidationError, match="unique"):
        MetadataWrite.model_validate(payload)


def test_whitespace_is_stripped() -> None:
    model = MetadataWrite.model_validate(
        sample_payload(table_name="  orders  ", owner="  data-eng  ")
    )
    assert model.table_name == "orders"
    assert model.owner == "data-eng"


def test_schema_alias_is_accepted() -> None:
    model = MetadataWrite.model_validate(sample_payload())
    dumped = model.model_dump(by_alias=True)
    assert dumped["schema"] == "public"
