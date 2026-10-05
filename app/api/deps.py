from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import DatabaseError
from app.database.mongodb import mongodb
from app.repositories.metadata_repository import MetadataRepository
from app.services.metadata_service import MetadataService


def get_database() -> AsyncIOMotorDatabase:
    if mongodb.database is None:
        raise DatabaseError("Database is not connected")
    return mongodb.database


def get_metadata_repository(
    database: AsyncIOMotorDatabase = Depends(get_database),
) -> MetadataRepository:
    return MetadataRepository(database)


def get_metadata_service(
    repository: MetadataRepository = Depends(get_metadata_repository),
) -> MetadataService:
    return MetadataService(repository)
