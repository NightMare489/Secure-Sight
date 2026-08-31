"""
Zone Repository.

Data access methods specific to Zone entities.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.zone import Zone
from app.repositories.base import BaseRepository


class ZoneRepository(BaseRepository[Zone]):
    """
    Repository for Zone CRUD and queries.

    Extends BaseRepository with zone-specific query methods.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, Zone)

    def get_by_camera_id(self, camera_id: str) -> list[Zone]:
        """Get all zones for a specific camera."""
        return (
            self._session.query(Zone)
            .filter(Zone.camera_id == camera_id)
            .order_by(Zone.created_at.asc())
            .all()
        )

    def get_active_by_camera_id(self, camera_id: str) -> list[Zone]:
        """Get all active zones for a specific camera."""
        return (
            self._session.query(Zone)
            .filter(Zone.camera_id == camera_id, Zone.is_active.is_(True))
            .order_by(Zone.created_at.asc())
            .all()
        )

    def count_by_camera_id(self, camera_id: str) -> int:
        """Count zones for a specific camera."""
        return (
            self._session.query(Zone)
            .filter(Zone.camera_id == camera_id)
            .count()
        )
