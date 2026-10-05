import os

import pytest
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.api.deps import get_database
from app.database.mongodb import ensure_indexes
from app.main import create_app
from app.repositories.metadata_repository import MetadataRepository
from app.services.metadata_service import MetadataService

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGO_TEST_DB = os.getenv("MONGODB_TEST_DB", "data_lake_catalog_test")
MONGO_REQUIRED = os.getenv("MONGODB_REQUIRED", "").lower() in {"1", "true", "yes"}


@pytest.fixture(scope="session")
def mongo_uri() -> str:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        if MONGO_REQUIRED:
            pytest.fail(f"MongoDB is required but unavailable: {exc}")
        pytest.skip(f"MongoDB is not available at {MONGO_URI}")
    finally:
        client.close()
    return MONGO_URI


@pytest.fixture
async def mongo_database(mongo_uri: str) -> AsyncIOMotorDatabase:
    client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=2000)
    database = client[MONGO_TEST_DB]
    await database["metadata"].drop()
    await database["metadata_history"].drop()
    await ensure_indexes(database)
    yield database
    await database["metadata"].drop()
    await database["metadata_history"].drop()
    client.close()


@pytest.fixture
def mongo_service(mongo_database: AsyncIOMotorDatabase) -> MetadataService:
    return MetadataService(MetadataRepository(mongo_database))


@pytest.fixture
async def mongo_client(mongo_database: AsyncIOMotorDatabase) -> AsyncClient:
    app = create_app(connect_db=False)
    app.dependency_overrides[get_database] = lambda: mongo_database
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
