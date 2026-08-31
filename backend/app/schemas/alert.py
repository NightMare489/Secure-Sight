"""
Alert Pydantic Schemas.

DTOs for alert query operations and API responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AlertResponse(BaseModel):
    """Schema for alert API responses."""

    id: str
    zone_id: str
    camera_id: str
    tracker_id: int
    global_person_id: Optional[str] = None
    association_confidence: Optional[float] = None
    association_method: Optional[str] = None
    event_type: str
    timestamp: datetime
    snapshot_path: Optional[str] = None
    zone_name: str = ""
    camera_name: str = ""

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    """Schema for listing alerts with pagination."""

    alerts: list[AlertResponse]
    total: int
    page: int
    per_page: int


class AlertFilter(BaseModel):
    """Schema for alert query filters."""

    camera_id: Optional[str] = None
    zone_id: Optional[str] = None
    event_type: Optional[str] = Field(
        None, pattern=r"^(ENTER|EXIT|PRESENT)$"
    )
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=200)
