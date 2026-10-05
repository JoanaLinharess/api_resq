from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings


async def ensure_indexes(database: AsyncIOMotorDatabase) -> None:
    collection = database["metadata"]
    await collection.create_index(
        [("database", 1), ("schema", 1), ("table_name", 1)],
        unique=True,
        name="uniq_table_identity",
    )
    await collection.create_index("table_name", name="idx_table_name")
    await collection.create_index("owner", name="idx_owner")
    await collection.create_index("domain", name="idx_domain")
    await collection.create_index("created_at", name="idx_created_at")

    history = database["metadata_history"]
    await history.create_index(
        [("metadata_id", 1), ("schema_version", 1)],
        unique=True,
        name="uniq_schema_version",
    )
    await history.create_index("metadata_id", name="idx_history_metadata_id")


class MongoDB:
    def __init__(self) -> None:
        self.client: AsyncIOMotorClient | None = None
        self.database: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.database = self.client[settings.mongodb_db]
        await ensure_indexes(self.database)

    async def disconnect(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None
            self.database = None


mongodb = MongoDB()
