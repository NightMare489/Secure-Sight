"""
Camera Service.

Business logic for camera management.
Validates inputs, orchestrates repository calls, and manages camera lifecycle.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.camera import Camera
from app.repositories.camera_repository import CameraRepository
from app.repositories.zone_repository import ZoneRepository
from app.schemas.camera import CameraCreate, CameraResponse, CameraUpdate
from app.utils.exceptions import DuplicateError, NotFoundError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CameraService:
    """
    Service for camera CRUD operations.

    Encapsulates business rules and validations for camera management.
    Depends on repositories (abstractions), not on the database directly.
    """

    def __init__(self, session: Session) -> None:
        self._camera_repo = CameraRepository(session)
        self._zone_repo = ZoneRepository(session)

    def get_all(self) -> list[CameraResponse]:
        """Get all cameras with zone counts."""
        cameras = self._camera_repo.get_all()
        return [self._to_response(cam) for cam in cameras]

    def get_by_id(self, camera_id: str) -> CameraResponse:
        """
        Get a camera by ID.

        Raises:
            NotFoundError: If camera doesn't exist.
        """
        camera = self._camera_repo.get_by_id(camera_id)
        if camera is None:
            raise NotFoundError("Camera", camera_id)
        return self._to_response(camera)

    def create(self, data: CameraCreate) -> CameraResponse:
        """
        Create a new camera.

        Raises:
            DuplicateError: If a camera with the same name exists.
        """
        existing = self._camera_repo.get_by_name(data.name)
        if existing is not None:
            raise DuplicateError("Camera", data.name)

        camera = Camera(
            name=data.name,
            source_uri=data.source_uri,
            source_type=data.source_type,
            description=data.description,
            is_active=data.is_active,
            overlap_group=data.overlap_group,
            ground_plane_homography=self._serialize_homography(
                data.ground_plane_homography
            ),
        )

        camera = self._camera_repo.create(camera)
        logger.info("Camera created: %s (id: %s)", camera.name, camera.id)
        return self._to_response(camera)

    def update(self, camera_id: str, data: CameraUpdate) -> CameraResponse:
        """
        Update an existing camera.

        Raises:
            NotFoundError: If camera doesn't exist.
            DuplicateError: If new name conflicts with another camera.
        """
        camera = self._camera_repo.get_by_id(camera_id)
        if camera is None:
            raise NotFoundError("Camera", camera_id)

        # Check name uniqueness if name is being changed
        if data.name is not None and data.name != camera.name:
            existing = self._camera_repo.get_by_name(data.name)
            if existing is not None:
                raise DuplicateError("Camera", data.name)

        # Apply partial update
        update_data = data.model_dump(exclude_unset=True)
        if "ground_plane_homography" in update_data:
            update_data["ground_plane_homography"] = self._serialize_homography(
                update_data["ground_plane_homography"]
            )
        for field, value in update_data.items():
            setattr(camera, field, value)

        camera = self._camera_repo.update(camera)
        logger.info("Camera updated: %s (id: %s)", camera.name, camera.id)
        return self._to_response(camera)

    def delete(self, camera_id: str) -> None:
        """
        Delete a camera and all its zones/alerts.

        Raises:
            NotFoundError: If camera doesn't exist.
        """
        camera = self._camera_repo.get_by_id(camera_id)
        if camera is None:
            raise NotFoundError("Camera", camera_id)

        self._camera_repo.delete(camera)
        logger.info("Camera deleted: %s (id: %s)", camera.name, camera.id)

    def _to_response(self, camera: Camera) -> CameraResponse:
        """Convert a Camera ORM model to a response DTO."""
        zone_count = self._zone_repo.count_by_camera_id(camera.id)

        return CameraResponse(
            id=camera.id,
            name=camera.name,
            source_uri=camera.source_uri,
            source_type=camera.source_type,
            description=camera.description or "",
            is_active=camera.is_active,
            overlap_group=camera.overlap_group,
            ground_plane_homography=self._deserialize_homography(
                camera.ground_plane_homography
            ),
            created_at=camera.created_at,
            updated_at=camera.updated_at,
            zone_count=zone_count,
        )

    @staticmethod
    def _serialize_homography(
        homography: list[list[float]] | None,
    ) -> str | None:
        return json.dumps(homography) if homography is not None else None

    @staticmethod
    def _deserialize_homography(
        homography: str | None,
    ) -> list[list[float]] | None:
        return json.loads(homography) if homography else None
