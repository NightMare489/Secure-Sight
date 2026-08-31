"""
Camera Repository.

Data access methods specific to Camera entities.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.camera import Camera
from app.repositories.base import BaseRepository


class CameraRepository(BaseRepository[Camera]):
    """
    Repository for Camera CRUD and queries.

    Extends BaseRepository with camera-specific query methods.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, Camera)

    def get_by_name(self, name: str) -> Camera | None:
        """Find a camera by its name."""
        return (
            self._session.query(Camera)
            .filter(Camera.name == name)
            .first()
        )

    def get_active(self) -> list[Camera]:
        """Get all active cameras."""
        return (
            self._session.query(Camera)
            .filter(Camera.is_active.is_(True))
            .order_by(Camera.created_at.desc())
            .all()
        )
