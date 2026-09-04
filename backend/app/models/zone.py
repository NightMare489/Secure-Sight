"""
Zone ORM Model.

Represents a polygon detection zone within a camera view.
Each camera can have multiple zones. Zone polygon points
are stored as normalized coordinates (0-1).
"""

from __future__ import annotations

import json

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Zone(Base, UUIDMixin, TimestampMixin):
    """
    Detection zone entity.

    Attributes:
        id: UUID primary key.
        camera_id: Foreign key to the parent camera.
        name: Human-readable zone name.
        polygon_points: JSON-encoded polygon vertices as normalized coords.
        color: Hex color string for rendering (e.g., "#FF0000").
        alert_enabled: Whether alerts are triggered for this zone.
        is_active: Whether the zone is currently active.
        camera: Parent Camera object.
        alerts: Related Alert objects.
    """

    __tablename__ = "zones"

    camera_id = Column(
        String(36),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    polygon_points = Column(Text, nullable=False)  # JSON string
    color = Column(String(7), nullable=False, default="#FF0000")
    alert_enabled = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True)
    rule_type = Column(String(20), nullable=False, default="intrusion")
    dwell_threshold_seconds = Column(Integer, nullable=True)
    occupancy_limit = Column(Integer, nullable=True)
    alert_cooldown_seconds = Column(Integer, nullable=False, default=60)

    # Relationships
    camera = relationship("Camera", back_populates="zones")
    alerts = relationship(
        "Alert",
        back_populates="zone",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def get_polygon(self) -> list[list[float]]:
        """Deserialize polygon_points JSON to a list of coordinate pairs."""
        return json.loads(self.polygon_points)

    def set_polygon(self, polygon: list[list[float]]) -> None:
        """Serialize polygon coordinate pairs to JSON."""
        self.polygon_points = json.dumps(polygon)

    def __repr__(self) -> str:
        return f"<Zone(id={self.id}, name={self.name}, camera_id={self.camera_id})>"
