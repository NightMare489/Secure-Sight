"""
Zone Pydantic Schemas.

DTOs for zone CRUD operations and API responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ZoneCreate(BaseModel):
    """Schema for creating a new zone."""

    name: str = Field(..., min_length=1, max_length=100)
    polygon_points: list[list[float]] = Field(
        ..., min_length=3, description="Polygon vertices as [[x,y], ...], normalized 0-1"
    )
    color: str = Field(default="#FF0000", pattern=r"^#[0-9A-Fa-f]{6}$")
    alert_enabled: bool = Field(default=True)
    is_active: bool = Field(default=True)
    rule_type: Literal["intrusion", "loitering", "occupancy_limit"] = "intrusion"
    dwell_threshold_seconds: Optional[int] = Field(None, ge=1, le=86400)
    occupancy_limit: Optional[int] = Field(None, ge=1, le=10000)
    alert_cooldown_seconds: int = Field(default=60, ge=0, le=86400)

    @field_validator("polygon_points")
    @classmethod
    def validate_polygon(cls, v: list[list[float]]) -> list[list[float]]:
        """Validate polygon has at least 3 points, each with x,y in [0,1]."""
        if len(v) < 3:
            raise ValueError("Polygon must have at least 3 points")

        for i, point in enumerate(v):
            if len(point) != 2:
                raise ValueError(
                    f"Point {i} must have exactly 2 coordinates [x, y]"
                )
            x, y = point
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(
                    f"Point {i} coordinates must be normalized (0-1), got [{x}, {y}]"
                )
        return v


class ZoneUpdate(BaseModel):
    """Schema for updating an existing zone (partial update)."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    polygon_points: Optional[list[list[float]]] = Field(None, min_length=3)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    alert_enabled: Optional[bool] = None
    is_active: Optional[bool] = None
    rule_type: Optional[Literal["intrusion", "loitering", "occupancy_limit"]] = None
    dwell_threshold_seconds: Optional[int] = Field(None, ge=1, le=86400)
    occupancy_limit: Optional[int] = Field(None, ge=1, le=10000)
    alert_cooldown_seconds: Optional[int] = Field(None, ge=0, le=86400)

    @field_validator("polygon_points")
    @classmethod
    def validate_polygon(
        cls, v: list[list[float]] | None
    ) -> list[list[float]] | None:
        """Validate polygon if provided."""
        if v is None:
            return v

        if len(v) < 3:
            raise ValueError("Polygon must have at least 3 points")

        for i, point in enumerate(v):
            if len(point) != 2:
                raise ValueError(
                    f"Point {i} must have exactly 2 coordinates [x, y]"
                )
            x, y = point
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(
                    f"Point {i} coordinates must be normalized (0-1)"
                )
        return v


class ZoneResponse(BaseModel):
    """Schema for zone API responses."""

    id: str
    camera_id: str
    name: str
    polygon_points: list[list[float]]
    color: str
    alert_enabled: bool
    is_active: bool
    rule_type: str
    dwell_threshold_seconds: Optional[int] = None
    occupancy_limit: Optional[int] = None
    alert_cooldown_seconds: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ZoneListResponse(BaseModel):
    """Schema for listing zones."""

    zones: list[ZoneResponse]
    total: int
