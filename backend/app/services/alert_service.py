"""
Alert Service.

Business logic for alert management.
Persists zone events, handles deduplication, and provides filtered queries.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.core.interfaces import ZoneEvent, ZoneEventType
from app.models.alert import Alert
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import AlertFilter, AlertListResponse, AlertResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


class AlertService:
    """
    Service for alert management.

    Handles persisting zone events as alerts, deduplication to prevent
    spam, and filtered/paginated queries.
    """

    def __init__(
        self,
        session: Session,
        snapshots_dir: Path | None = None,
    ) -> None:
        self._alert_repo = AlertRepository(session)
        self._snapshots_dir = snapshots_dir
        self._session = session

        # Deduplication: track recent events to prevent spamming
        # Key: (zone_id, globally associated person, event type), Value: timestamp
        self._recent_events: dict[tuple[str, str, ZoneEventType], float] = {}
        self._dedup_cooldown: float = 5.0  # Seconds between alerts for same person+zone

    def process_zone_event(
        self, event: ZoneEvent, camera_id: str
    ) -> AlertResponse | None:
        """
        Process a zone event and persist it as an alert.

        Applies deduplication to prevent flooding the database
        with alerts for the same person in the same zone.

        Args:
            event: The zone event from the detection pipeline.
            camera_id: The camera that generated the event.

        Returns:
            AlertResponse if the event was persisted, None if deduplicated.
        """
        # Only persist ENTER and EXIT events (PRESENT events are informational heartbeats)
        if event.event_type not in (ZoneEventType.ENTER, ZoneEventType.EXIT):
            return None

        # Deduplication check
        person_key = event.global_person_id or f"{camera_id}:{event.tracker_id}"
        dedup_key = (event.zone_id, person_key, event.event_type)
        now = time.time()

        if dedup_key in self._recent_events:
            last_time = self._recent_events[dedup_key]
            if now - last_time < self._dedup_cooldown:
                return None  # Skip — too recent

        self._recent_events[dedup_key] = now

        # Save snapshot if available (only for ENTER events to save disk space)
        snapshot_path = None
        if event.event_type == ZoneEventType.ENTER and event.snapshot is not None and self._snapshots_dir is not None:
            snapshot_path = self._save_snapshot(
                event.snapshot, camera_id, event.zone_id
            )

        # Create alert
        alert = Alert(
            zone_id=event.zone_id,
            camera_id=camera_id,
            tracker_id=event.tracker_id,
            global_person_id=event.global_person_id,
            association_confidence=event.association_confidence,
            association_method=event.association_method,
            event_type=event.event_type.value,
            timestamp=datetime.fromtimestamp(event.timestamp, tz=timezone.utc),
            snapshot_path=snapshot_path,
        )

        alert = self._alert_repo.create(alert)

        action_word = "entered" if event.event_type == ZoneEventType.ENTER else "exited"
        logger.info(
            "Alert created: Person %d %s zone '%s' on camera %s",
            event.tracker_id,
            action_word,
            event.zone_name,
            camera_id,
        )

        return self._to_response(alert)

    def get_alerts(self, filters: AlertFilter) -> AlertListResponse:
        """
        Get filtered and paginated alerts.

        Args:
            filters: Alert filter criteria.

        Returns:
            Paginated alert list response.
        """
        alerts, total = self._alert_repo.get_filtered(
            camera_id=filters.camera_id,
            zone_id=filters.zone_id,
            event_type=filters.event_type,
            start_time=filters.start_time,
            end_time=filters.end_time,
            page=filters.page,
            per_page=filters.per_page,
        )

        return AlertListResponse(
            alerts=[self._to_response(a) for a in alerts],
            total=total,
            page=filters.page,
            per_page=filters.per_page,
        )

    def get_by_id(self, alert_id: str) -> AlertResponse:
        """Get a specific alert by ID."""
        from app.utils.exceptions import NotFoundError

        alert = self._alert_repo.get_by_id(alert_id)
        if alert is None:
            raise NotFoundError("Alert", alert_id)
        return self._to_response(alert)

    def get_recent(self, limit: int = 20) -> list[AlertResponse]:
        """Get the most recent alerts."""
        alerts = self._alert_repo.get_recent(limit)
        return [self._to_response(a) for a in alerts]

    def _save_snapshot(
        self, frame: np.ndarray, camera_id: str, zone_id: str
    ) -> str | None:
        """Save a frame snapshot and return the file path."""
        if self._snapshots_dir is None:
            return None

        try:
            self._snapshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time() * 1000)
            filename = f"{camera_id}_{zone_id}_{timestamp}.jpg"
            filepath = self._snapshots_dir / filename

            cv2.imwrite(str(filepath), frame)
            return str(filepath)
        except Exception as e:
            logger.error("Failed to save snapshot: %s", e)
            return None

    def _to_response(self, alert: Alert) -> AlertResponse:
        """Convert an Alert ORM model to a response DTO."""
        zone_name = ""
        camera_name = ""

        if alert.zone:
            zone_name = alert.zone.name
        if alert.camera:
            camera_name = alert.camera.name

        return AlertResponse(
            id=alert.id,
            zone_id=alert.zone_id,
            camera_id=alert.camera_id,
            tracker_id=alert.tracker_id,
            global_person_id=alert.global_person_id,
            association_confidence=alert.association_confidence,
            association_method=alert.association_method,
            event_type=alert.event_type,
            timestamp=alert.timestamp,
            snapshot_path=alert.snapshot_path,
            zone_name=zone_name,
            camera_name=camera_name,
        )

    def cleanup_dedup_cache(self) -> None:
        """Remove expired entries from the deduplication cache."""
        now = time.time()
        expired = [
            key
            for key, ts in self._recent_events.items()
            if now - ts > self._dedup_cooldown * 10
        ]
        for key in expired:
            del self._recent_events[key]
