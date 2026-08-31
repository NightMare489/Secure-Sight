"""
Camera Pydantic Schemas.

DTOs for camera CRUD operations and API responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CameraCreate(BaseModel):
    """Schema for creating a new camera."""

    name: str = Field(..., min_length=1, max_length=100)
    source_uri: str = Field(..., min_length=1, max_length=500)
    source_type: str = Field(default="file", pattern=r"^(file|rtsp|webcam)$")
    description: str = Field(default="", max_length=500)
    is_active: bool = Field(default=True)
    overlap_group: Optional[str] = Field(None, max_length=100)
    ground_plane_homography: Optional[list[list[float]]] = None

    @field_validator("ground_plane_homography")
    @classmethod
    def validate_homography(
        cls, value: list[list[float]] | None
    ) -> list[list[float]] | None:
        if value is None:
            return value
        if len(value) != 3 or any(len(row) != 3 for row in value):
            raise ValueError("ground_plane_homography must be a 3x3 matrix")
        return value


class CameraUpdate(BaseModel):
    """Schema for updating an existing camera (partial update)."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    source_uri: Optional[str] = Field(None, min_length=1, max_length=500)
    source_type: Optional[str] = Field(
        None, pattern=r"^(file|rtsp|webcam)$"
    )
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    overlap_group: Optional[str] = Field(None, max_length=100)
    ground_plane_homography: Optional[list[list[float]]] = None

    @field_validator("ground_plane_homography")
    @classmethod
    def validate_homography(
        cls, value: list[list[float]] | None
    ) -> list[list[float]] | None:
        return CameraCreate.validate_homography(value)


class CameraResponse(BaseModel):
    """Schema for camera API responses."""

    id: str
    name: str
    source_uri: str
    source_type: str
    description: str
    is_active: bool
    overlap_group: Optional[str] = None
    ground_plane_homography: Optional[list[list[float]]] = None
    created_at: datetime
    updated_at: datetime
    zone_count: int = 0
    pipeline_status: str = "IDLE"

    model_config = {"from_attributes": True}


class CameraListResponse(BaseModel):
    """Schema for listing cameras."""

    cameras: list[CameraResponse]
    total: int
