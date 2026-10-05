from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import sample_payload


def test_health_without_database() -> None:
    client = TestClient(create_app(connect_db=False))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["detail"] == "Database is not connected"


def test_create_and_get_metadata(client: TestClient) -> None:
    created = client.post("/metadata", json=sample_payload())
    assert created.status_code == 201
    body = created.json()
    assert body["table_name"] == "orders"
    assert body["schema"] == "public"
    assert body["schema_version"] == 1
    assert "id" in body

    fetched = client.get(f"/metadata/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_list_metadata_with_filters(client: TestClient) -> None:
    client.post("/metadata", json=sample_payload())
    client.post(
        "/metadata",
        json=sample_payload(table_name="customers", owner="analytics", domain="crm"),
    )

    response = client.get("/metadata", params={"table_name": "ord", "page": 1, "page_size": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["table_name"] == "orders"


def test_update_and_delete_metadata(client: TestClient) -> None:
    created = client.post("/metadata", json=sample_payload()).json()
    updated = client.put(
        f"/metadata/{created['id']}",
        json=sample_payload(
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
    assert updated.status_code == 200
    assert updated.json()["schema_version"] == 2
    assert updated.json()["description"] == "Updated"

    history = client.get(f"/metadata/{created['id']}/history")
    assert history.status_code == 200
    versions = [item["schema_version"] for item in history.json()["items"]]
    assert versions == [1, 2]

    deleted = client.delete(f"/metadata/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/metadata/{created['id']}").status_code == 404


def test_history_not_found(client: TestClient) -> None:
    response = client.get(f"/metadata/{ObjectId()}/history")
    assert response.status_code == 404


def test_not_found(client: TestClient) -> None:
    response = client.get(f"/metadata/{ObjectId()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Metadata not found"


def test_invalid_id(client: TestClient) -> None:
    response = client.get("/metadata/invalid-id")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid metadata id"


def test_conflict_on_duplicate_identity(client: TestClient) -> None:
    assert client.post("/metadata", json=sample_payload()).status_code == 201
    conflict = client.post("/metadata", json=sample_payload())
    assert conflict.status_code == 409


def test_validation_error(client: TestClient) -> None:
    payload = sample_payload(table_name="")
    response = client.post("/metadata", json=payload)
    assert response.status_code == 422


def test_duplicate_columns_validation(client: TestClient) -> None:
    payload = sample_payload(
        columns=[
            {"name": "id", "type": "string", "description": "", "nullable": False},
            {"name": "id", "type": "int", "description": "", "nullable": True},
        ]
    )
    response = client.post("/metadata", json=payload)
    assert response.status_code == 422


def test_invalid_pagination(client: TestClient) -> None:
    response = client.get("/metadata", params={"page": 0})
    assert response.status_code == 422
