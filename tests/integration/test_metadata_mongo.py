import pytest
from bson import ObjectId
from httpx import AsyncClient

from app.core.exceptions import ConflictError, InvalidIdError, NotFoundError
from app.schemas.metadata import MetadataWrite
from app.services.metadata_service import MetadataService
from tests.conftest import sample_payload

pytestmark = pytest.mark.mongo


def _write(**overrides) -> MetadataWrite:
    return MetadataWrite.model_validate(sample_payload(**overrides))


async def test_create_and_get_by_id(mongo_service: MetadataService) -> None:
    created = await mongo_service.create(_write())
    found = await mongo_service.get_by_id(created.id)

    assert found.id == created.id
    assert found.table_name == "orders"
    assert found.schema_name == "public"
    assert found.schema_version == 1
    assert len(found.columns) == 2


async def test_duplicate_identity_is_conflict(mongo_service: MetadataService) -> None:
    await mongo_service.create(_write())
    with pytest.raises(ConflictError):
        await mongo_service.create(_write())


async def test_unique_index_blocks_same_table_identity(
    mongo_service: MetadataService,
) -> None:
    await mongo_service.create(_write())
    with pytest.raises(ConflictError):
        await mongo_service.create(_write(description="another catalog entry"))


async def test_list_filters_and_pagination(mongo_service: MetadataService) -> None:
    await mongo_service.create(_write())
    await mongo_service.create(
        _write(table_name="customers", owner="analytics", domain="crm")
    )

    by_name = await mongo_service.list_metadata(table_name="ord")
    assert by_name.total == 1
    assert by_name.items[0].table_name == "orders"

    by_owner = await mongo_service.list_metadata(owner="ANALYTICS")
    assert by_owner.total == 1

    page = await mongo_service.list_metadata(page=1, page_size=1)
    assert page.total == 2
    assert len(page.items) == 1


async def test_update_persists_and_bumps_schema_version(
    mongo_service: MetadataService,
) -> None:
    created = await mongo_service.create(_write())
    updated = await mongo_service.update(
        created.id,
        _write(
            description="Updated",
            columns=[
                {
                    "name": "order_id",
                    "type": "bigint",
                    "description": "Order identifier",
                    "nullable": False,
                }
            ],
        ),
    )
    reloaded = await mongo_service.get_by_id(created.id)

    assert updated.schema_version == 2
    assert reloaded.schema_version == 2
    assert reloaded.description == "Updated"
    assert reloaded.columns[0].type == "bigint"
    history = await mongo_service.get_history(created.id)
    assert [item.schema_version for item in history] == [1, 2]
    assert history[0].columns[0].type == "string"
    assert history[1].columns[0].type == "bigint"


async def test_update_identity_conflict(mongo_service: MetadataService) -> None:
    first = await mongo_service.create(_write())
    second = await mongo_service.create(_write(table_name="customers"))

    with pytest.raises(ConflictError):
        await mongo_service.update(second.id, _write(table_name=first.table_name))


async def test_delete_and_missing_record(mongo_service: MetadataService) -> None:
    created = await mongo_service.create(_write())
    await mongo_service.delete(created.id)

    with pytest.raises(NotFoundError):
        await mongo_service.get_by_id(created.id)
    with pytest.raises(NotFoundError):
        await mongo_service.delete(str(ObjectId()))


async def test_invalid_id(mongo_service: MetadataService) -> None:
    with pytest.raises(InvalidIdError):
        await mongo_service.get_by_id("not-an-id")


async def test_http_create_get_conflict_and_delete(mongo_client: AsyncClient) -> None:
    created = await mongo_client.post("/metadata", json=sample_payload())
    assert created.status_code == 201
    metadata_id = created.json()["id"]

    fetched = await mongo_client.get(f"/metadata/{metadata_id}")
    assert fetched.status_code == 200
    assert fetched.json()["table_name"] == "orders"

    conflict = await mongo_client.post("/metadata", json=sample_payload())
    assert conflict.status_code == 409

    deleted = await mongo_client.delete(f"/metadata/{metadata_id}")
    assert deleted.status_code == 204
    missing = await mongo_client.get(f"/metadata/{metadata_id}")
    assert missing.status_code == 404
