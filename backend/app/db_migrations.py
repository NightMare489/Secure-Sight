"""Small additive migrations for installations created before Alembic is used.

The project historically creates its SQLite schema with ``create_all``. That
creates new tables but cannot add columns to a database that already exists.
These migrations are deliberately additive and idempotent.
"""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from app.utils.logger import get_logger

logger = get_logger(__name__)


_SQLITE_COLUMNS: dict[str, dict[str, str]] = {
    "cameras": {
        "overlap_group": "VARCHAR(100)",
        "ground_plane_homography": "TEXT",
    },
    "alerts": {
        "global_person_id": "VARCHAR(36)",
        "association_confidence": "FLOAT",
        "association_method": "VARCHAR(30)",
    },
}


def apply_additive_migrations(engine: Engine) -> None:
    """Add currently required nullable columns to an existing SQLite DB."""
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    with engine.begin() as connection:
        for table_name, columns in _SQLITE_COLUMNS.items():
            if table_name not in inspector.get_table_names():
                continue
            existing = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column_name, column_type in columns.items():
                if column_name in existing:
                    continue
                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        f"ADD COLUMN {column_name} {column_type}"
                    )
                )
                logger.info("Migrated SQLite table %s: added %s", table_name, column_name)
