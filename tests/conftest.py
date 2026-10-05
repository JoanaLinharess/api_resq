import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_metadata_service
from app.main import create_app
from app.services.metadata_service import MetadataService
from tests.fakes import InMemoryMetadataRepository


@pytest.fixture
def repository() -> InMemoryMetadataRepository:
    return InMemoryMetadataRepository()


@pytest.fixture
def service(repository: InMemoryMetadataRepository) -> MetadataService:
    return MetadataService(repository)


@pytest.fixture
def client(service: MetadataService) -> TestClient:
    app = create_app(connect_db=False)
    app.dependency_overrides[get_metadata_service] = lambda: service
    return TestClient(app)


def sample_payload(**overrides) -> dict:
    payload = {
        "table_name": "orders",
        "description": "Customer orders",
        "database": "sales",
        "schema": "public",
        "owner": "data-eng",
        "domain": "commerce",
        "columns": [
            {
                "name": "order_id",
                "type": "string",
                "description": "Order identifier",
                "nullable": False,
            },
            {
                "name": "amount",
                "type": "decimal",
                "description": "Order amount",
                "nullable": True,
            },
        ],
    }
    payload.update(overrides)
    return payload
