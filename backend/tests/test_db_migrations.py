from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from app.db_migrations import apply_additive_migrations


def test_additive_migration_updates_existing_sqlite_tables(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'schoolcv.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE cameras (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE alerts (id VARCHAR(36) PRIMARY KEY)"))

    apply_additive_migrations(engine)

    inspector = inspect(engine)
    camera_columns = {column["name"] for column in inspector.get_columns("cameras")}
    alert_columns = {column["name"] for column in inspector.get_columns("alerts")}

    assert {"overlap_group", "ground_plane_homography"} <= camera_columns
    assert {
        "global_person_id",
        "association_confidence",
        "association_method",
    } <= alert_columns
