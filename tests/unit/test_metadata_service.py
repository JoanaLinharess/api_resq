import pytest
from bson import ObjectId
from pydantic import ValidationError

from app.core.exceptions import ConflictError, InvalidIdError, NotFoundError
from app.schemas.metadata import MetadataWrite
from app.services.metadata_service import MetadataService
from tests.conftest import sample_payload
from tests.fakes import InMemoryMetadataRepository


def _write(**overrides) -> MetadataWrite:
    return MetadataWrite.model_validate(sample_payload(**overrides))


async def test_create_metadata(service: MetadataService) -> None:
    created = await service.create(_write())
    assert created.id is not None
    assert created.schema_version == 1
    assert created.table_name == "orders"
    assert created.schema_name == "public"


async def test_create_conflict(service: MetadataService) -> None:
    await service.create(_write())
    with pytest.raises(ConflictError):
        await service.create(_write())


async def test_get_by_id(service: MetadataService) -> None:
    created = await service.create(_write())
    found = await service.get_by_id(created.id)
    assert found.table_name == "orders"


async def test_get_missing_id(service: MetadataService) -> None:
    with pytest.raises(NotFoundError):
        await service.get_by_id(str(ObjectId()))


async def test_get_invalid_id(service: MetadataService) -> None:
    with pytest.raises(InvalidIdError):
        await service.get_by_id("not-an-id")


async def test_list_filters(service: MetadataService) -> None:
    await service.create(_write())
    await service.create(
        _write(table_name="customers", owner="analytics", domain="crm")
    )

    by_name = await service.list_metadata(table_name="ord")
    assert by_name.total == 1
    assert by_name.items[0].table_name == "orders"

    by_owner = await service.list_metadata(owner="analytics")
    assert by_owner.total == 1
    assert by_owner.items[0].table_name == "customers"

    by_domain = await service.list_metadata(domain="commerce")
    assert by_domain.total == 1


async def test_list_pagination(service: MetadataService) -> None:
    await service.create(_write(table_name="orders"))
    await service.create(_write(table_name="customers", database="crm"))

    page = await service.list_metadata(page=1, page_size=1)
    assert page.total == 2
    assert len(page.items) == 1
    assert page.page == 1
    assert page.page_size == 1


async def test_update_increments_schema_version(service: MetadataService) -> None:
    created = await service.create(_write())
    updated = await service.update(
        created.id,
        _write(
            columns=[
                {
                    "name": "order_id",
                    "type": "int",
                    "description": "Order identifier",
                    "nullable": False,
                }
            ]
        ),
    )
    assert updated.schema_version == 2
    assert updated.columns[0].type == "int"
    history = await service.get_history(created.id)
    assert [item.schema_version for item in history] == [1, 2]
    assert history[0].columns[0].type == "string"
    assert history[1].columns[0].type == "int"


async def test_update_without_structural_change_keeps_version(
    service: MetadataService,
) -> None:
    created = await service.create(_write())
    updated = await service.update(
        created.id, _write(description="New catalog description")
    )
    assert updated.schema_version == 1
    assert updated.description == "New catalog description"
    history = await service.get_history(created.id)
    assert len(history) == 1
    assert history[0].schema_version == 1


async def test_update_identity_conflict(service: MetadataService) -> None:
    first = await service.create(_write())
    second = await service.create(_write(table_name="customers"))
    with pytest.raises(ConflictError):
        await service.update(
            second.id,
            _write(table_name=first.table_name),
        )


async def test_update_missing(service: MetadataService) -> None:
    with pytest.raises(NotFoundError):
        await service.update(str(ObjectId()), _write())


async def test_delete_metadata(
    service: MetadataService, repository: InMemoryMetadataRepository
) -> None:
    created = await service.create(_write())
    await service.delete(created.id)
    with pytest.raises(NotFoundError):
        await service.get_by_id(created.id)
    with pytest.raises(NotFoundError):
        await service.get_history(created.id)
    assert await repository.list_history(created.id) == []


async def test_delete_missing(service: MetadataService) -> None:
    with pytest.raises(NotFoundError):
        await service.delete(str(ObjectId()))


def test_invalid_payload_is_rejected_before_service() -> None:
    with pytest.raises(ValidationError):
        _write(table_name="")
