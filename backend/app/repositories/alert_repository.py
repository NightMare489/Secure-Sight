"""
Alert Repository.

Data access methods specific to Alert entities.
Includes filtering and pagination support.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.repositories.base import BaseRepository


class AlertRepository(BaseRepository[Alert]):
    """
    Repository for Alert CRUD and queries.

    Extends BaseRepository with alert-specific filtering
    and pagination capabilities.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, Alert)

    def get_filtered(
        self,
        camera_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[Alert], int]:
        """
        Get alerts with filtering and pagination.

        Args:
            camera_id: Filter by camera ID.
            zone_id: Filter by zone ID.
            event_type: Filter by event type (ENTER, EXIT, PRESENT).
            start_time: Filter alerts after this time.
            end_time: Filter alerts before this time.
            page: Page number (1-indexed).
            per_page: Items per page.

        Returns:
            Tuple of (list of alerts, total count).
        """
        query = self._session.query(Alert)

        if camera_id:
            query = query.filter(Alert.camera_id == camera_id)
        if zone_id:
            query = query.filter(Alert.zone_id == zone_id)
        if event_type:
            query = query.filter(Alert.event_type == event_type)
        if start_time:
            query = query.filter(Alert.timestamp >= start_time)
        if end_time:
            query = query.filter(Alert.timestamp <= end_time)

        total = query.count()

        alerts = (
            query.order_by(desc(Alert.timestamp))
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return alerts, total

    def get_recent(self, limit: int = 20) -> list[Alert]:
        """Get the most recent alerts."""
        return (
            self._session.query(Alert)
            .order_by(desc(Alert.timestamp))
            .limit(limit)
            .all()
        )

    def get_by_camera_id(
        self, camera_id: str, limit: int = 50
    ) -> list[Alert]:
        """Get recent alerts for a specific camera."""
        return (
            self._session.query(Alert)
            .filter(Alert.camera_id == camera_id)
            .order_by(desc(Alert.timestamp))
            .limit(limit)
            .all()
        )
