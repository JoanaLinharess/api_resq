from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_metadata_service
from app.models.metadata import Column, Metadata, SchemaSnapshot
from app.schemas.metadata import (
    MetadataListResponse,
    MetadataResponse,
    MetadataWrite,
    SchemaHistoryResponse,
    SchemaSnapshotResponse,
)
from app.services.metadata_service import MetadataService

router = APIRouter(prefix="/metadata", tags=["metadata"])


def to_response(entity: Metadata) -> MetadataResponse:
    return MetadataResponse(
        id=entity.id,
        table_name=entity.table_name,
        description=entity.description,
        database=entity.database,
        schema_name=entity.schema_name,
        owner=entity.owner,
        domain=entity.domain,
        columns=_columns_payload(entity.columns),
        schema_version=entity.schema_version,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.post("", response_model=MetadataResponse, status_code=status.HTTP_201_CREATED)
async def create_metadata(
    payload: MetadataWrite,
    service: MetadataService = Depends(get_metadata_service),
) -> MetadataResponse:
    return to_response(await service.create(payload))


@router.get("", response_model=MetadataListResponse)
async def list_metadata(
    table_name: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: MetadataService = Depends(get_metadata_service),
) -> MetadataListResponse:
    result = await service.list_metadata(
        table_name=table_name,
        owner=owner,
        domain=domain,
        page=page,
        page_size=page_size,
    )
    return MetadataListResponse(
        items=[to_response(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


def _columns_payload(columns: list[Column]) -> list[dict]:
    return [
        {
            "name": column.name,
            "type": column.type,
            "description": column.description,
            "nullable": column.nullable,
        }
        for column in columns
    ]


def to_history_response(metadata_id: str, snapshots: list[SchemaSnapshot]) -> SchemaHistoryResponse:
    return SchemaHistoryResponse(
        metadata_id=metadata_id,
        items=[
            SchemaSnapshotResponse(
                schema_version=snapshot.schema_version,
                columns=_columns_payload(snapshot.columns),
                recorded_at=snapshot.recorded_at,
            )
            for snapshot in snapshots
        ],
    )


@router.get("/{metadata_id}/history", response_model=SchemaHistoryResponse)
async def get_metadata_history(
    metadata_id: str,
    service: MetadataService = Depends(get_metadata_service),
) -> SchemaHistoryResponse:
    return to_history_response(metadata_id, await service.get_history(metadata_id))


@router.get("/{metadata_id}", response_model=MetadataResponse)
async def get_metadata(
    metadata_id: str,
    service: MetadataService = Depends(get_metadata_service),
) -> MetadataResponse:
    return to_response(await service.get_by_id(metadata_id))


@router.put("/{metadata_id}", response_model=MetadataResponse)
async def update_metadata(
    metadata_id: str,
    payload: MetadataWrite,
    service: MetadataService = Depends(get_metadata_service),
) -> MetadataResponse:
    return to_response(await service.update(metadata_id, payload))


@router.delete("/{metadata_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metadata(
    metadata_id: str,
    service: MetadataService = Depends(get_metadata_service),
) -> Response:
    await service.delete(metadata_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
