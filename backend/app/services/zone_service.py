"""
Zone Service.

Business logic for zone management.
Validates polygon geometry, handles zone CRUD, and converts between formats.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.zone import Zone
from app.repositories.camera_repository import CameraRepository
from app.repositories.zone_repository import ZoneRepository
from app.schemas.zone import ZoneCreate, ZoneResponse, ZoneUpdate
from app.core.interfaces import ZoneDefinition
from app.utils.exceptions import NotFoundError, ValidationError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ZoneService:
    """
    Service for zone CRUD operations.

    Handles zone creation, updates, and deletion. Validates
    polygon geometry and ensures parent camera exists.
    """

    def __init__(self, session: Session) -> None:
        self._zone_repo = ZoneRepository(session)
        self._camera_repo = CameraRepository(session)

    def get_by_camera_id(self, camera_id: str) -> list[ZoneResponse]:
        """
        Get all zones for a camera.

        Raises:
            NotFoundError: If camera doesn't exist.
        """
        camera = self._camera_repo.get_by_id(camera_id)
        if camera is None:
            raise NotFoundError("Camera", camera_id)

        zones = self._zone_repo.get_by_camera_id(camera_id)
        return [self._to_response(z) for z in zones]

    def get_by_id(self, zone_id: str) -> ZoneResponse:
        """
        Get a zone by ID.

        Raises:
            NotFoundError: If zone doesn't exist.
        """
        zone = self._zone_repo.get_by_id(zone_id)
        if zone is None:
            raise NotFoundError("Zone", zone_id)
        return self._to_response(zone)

    def create(self, camera_id: str, data: ZoneCreate) -> ZoneResponse:
        """
        Create a new zone for a camera.

        Raises:
            NotFoundError: If camera doesn't exist.
            ValidationError: If polygon is invalid.
        """
        camera = self._camera_repo.get_by_id(camera_id)
        if camera is None:
            raise NotFoundError("Camera", camera_id)

        zone = Zone(
            camera_id=camera_id,
            name=data.name,
            polygon_points=json.dumps(data.polygon_points),
            color=data.color,
            alert_enabled=data.alert_enabled,
            is_active=data.is_active,
            rule_type=data.rule_type,
            dwell_threshold_seconds=data.dwell_threshold_seconds,
            occupancy_limit=data.occupancy_limit,
            alert_cooldown_seconds=data.alert_cooldown_seconds,
        )

        zone = self._zone_repo.create(zone)
        logger.info(
            "Zone created: %s for camera %s (id: %s)",
            zone.name,
            camera_id,
            zone.id,
        )
        return self._to_response(zone)

    def update(self, zone_id: str, data: ZoneUpdate) -> ZoneResponse:
        """
        Update an existing zone.

        Raises:
            NotFoundError: If zone doesn't exist.
        """
        zone = self._zone_repo.get_by_id(zone_id)
        if zone is None:
            raise NotFoundError("Zone", zone_id)

        update_data = data.model_dump(exclude_unset=True)

        # Handle polygon_points serialization
        if "polygon_points" in update_data and update_data["polygon_points"] is not None:
            update_data["polygon_points"] = json.dumps(
                update_data["polygon_points"]
            )

        for field, value in update_data.items():
            setattr(zone, field, value)

        zone = self._zone_repo.update(zone)
        logger.info("Zone updated: %s (id: %s)", zone.name, zone.id)
        return self._to_response(zone)

    def delete(self, zone_id: str) -> None:
        """
        Delete a zone.

        Raises:
            NotFoundError: If zone doesn't exist.
        """
        zone = self._zone_repo.get_by_id(zone_id)
        if zone is None:
            raise NotFoundError("Zone", zone_id)

        self._zone_repo.delete(zone)
        logger.info("Zone deleted: %s (id: %s)", zone.name, zone.id)

    def get_zone_definitions(self, camera_id: str) -> list[ZoneDefinition]:
        """
        Get active zones as ZoneDefinition DTOs for the detection pipeline.

        Args:
            camera_id: Camera to get zones for.

        Returns:
            List of ZoneDefinition objects for the core engine.
        """
        zones = self._zone_repo.get_active_by_camera_id(camera_id)

        return [
            ZoneDefinition(
                zone_id=z.id,
                name=z.name,
                polygon=z.get_polygon(),
                color=z.color,
                is_active=z.is_active and z.alert_enabled,
                rule_type=z.rule_type,
                dwell_threshold_seconds=z.dwell_threshold_seconds,
                occupancy_limit=z.occupancy_limit,
                alert_cooldown_seconds=z.alert_cooldown_seconds,
            )
            for z in zones
        ]

    def _to_response(self, zone: Zone) -> ZoneResponse:
        """Convert a Zone ORM model to a response DTO."""
        return ZoneResponse(
            id=zone.id,
            camera_id=zone.camera_id,
            name=zone.name,
            polygon_points=zone.get_polygon(),
            color=zone.color,
            alert_enabled=zone.alert_enabled,
            is_active=zone.is_active,
            rule_type=zone.rule_type,
            dwell_threshold_seconds=zone.dwell_threshold_seconds,
            occupancy_limit=zone.occupancy_limit,
            alert_cooldown_seconds=zone.alert_cooldown_seconds,
            created_at=zone.created_at,
            updated_at=zone.updated_at,
        )
