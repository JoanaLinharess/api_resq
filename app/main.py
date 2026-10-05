from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.metadata import router as metadata_router
from app.core.exceptions import ConflictError, DatabaseError, InvalidIdError, NotFoundError
from app.database.mongodb import mongodb


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await mongodb.connect()
    yield
    await mongodb.disconnect()


def create_app(*, connect_db: bool = True) -> FastAPI:
    application = FastAPI(
        title="Data Lake Metadata Catalog",
        description="REST API for table metadata in a Data Lake catalog.",
        version="1.0.0",
        lifespan=lifespan if connect_db else None,
    )
    _register_exception_handlers(application)
    application.include_router(metadata_router)

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        if mongodb.database is None:
            raise DatabaseError("Database is not connected")
        try:
            await mongodb.database.command("ping")
        except Exception as exc:
            raise DatabaseError("Database unavailable") from exc
        return {"status": "ok"}

    return application


def _register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.message})

    @application.exception_handler(ConflictError)
    async def conflict_handler(_request: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": exc.message})

    @application.exception_handler(InvalidIdError)
    async def invalid_id_handler(_request: Request, exc: InvalidIdError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.message})

    @application.exception_handler(DatabaseError)
    async def database_handler(_request: Request, exc: DatabaseError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": exc.message})


app = create_app()
