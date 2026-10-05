from app.models.metadata import Column, Metadata


def _metadata(columns: list[Column] | None = None) -> Metadata:
    return Metadata.new(
        table_name="orders",
        description="Orders",
        database="sales",
        schema_name="public",
        owner="data-eng",
        domain="commerce",
        columns=columns
        or [
            Column("order_id", "string", "id", False),
            Column("amount", "decimal", "value", True),
        ],
    )


def test_new_metadata_starts_at_version_one() -> None:
    entity = _metadata()
    assert entity.schema_version == 1
    assert entity.id is None


def test_update_without_structural_change_keeps_version() -> None:
    entity = _metadata()
    entity.apply_update(
        table_name="orders",
        description="Updated description",
        database="sales",
        schema_name="public",
        owner="analytics",
        domain="commerce",
        columns=[
            Column("order_id", "string", "new description", False),
            Column("amount", "decimal", "value", True),
        ],
    )
    assert entity.schema_version == 1
    assert entity.owner == "analytics"
    assert entity.description == "Updated description"


def test_update_with_type_change_increments_version() -> None:
    entity = _metadata()
    entity.apply_update(
        table_name="orders",
        description="Orders",
        database="sales",
        schema_name="public",
        owner="data-eng",
        domain="commerce",
        columns=[
            Column("order_id", "int", "id", False),
            Column("amount", "decimal", "value", True),
        ],
    )
    assert entity.schema_version == 2


def test_update_with_added_column_increments_version() -> None:
    entity = _metadata()
    entity.apply_update(
        table_name="orders",
        description="Orders",
        database="sales",
        schema_name="public",
        owner="data-eng",
        domain="commerce",
        columns=[
            Column("order_id", "string", "id", False),
            Column("amount", "decimal", "value", True),
            Column("status", "string", "status", True),
        ],
    )
    assert entity.schema_version == 2


def test_column_order_does_not_count_as_structural_change() -> None:
    entity = _metadata()
    entity.apply_update(
        table_name="orders",
        description="Orders",
        database="sales",
        schema_name="public",
        owner="data-eng",
        domain="commerce",
        columns=[
            Column("amount", "decimal", "value", True),
            Column("order_id", "string", "id", False),
        ],
    )
    assert entity.schema_version == 1
