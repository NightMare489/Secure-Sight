"""
Camera ORM Model.

Represents a physical camera source in the system.
Each camera can have multiple detection zones.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Camera(Base, UUIDMixin, TimestampMixin):
    """
    Camera entity.

    Attributes:
        id: UUID primary key.
        name: Human-readable camera name.
        source_uri: Video source URI (file path, RTSP URL, etc.).
        source_type: Type of source ("file", "rtsp", "webcam").
        description: Optional description of the camera/location.
        is_active: Whether the camera is enabled.
        zones: Related Zone objects.
        alerts: Related Alert objects.
    """

    __tablename__ = "cameras"

    name = Column(String(100), nullable=False)
    source_uri = Column(String(500), nullable=False)
    source_type = Column(String(20), nullable=False, default="file")
    description = Column(String(500), nullable=True, default="")
    is_active = Column(Boolean, nullable=False, default=True)
    overlap_group = Column(String(100), nullable=True)
    ground_plane_homography = Column(Text, nullable=True)

    # Relationships
    zones = relationship(
        "Zone",
        back_populates="camera",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    alerts = relationship(
        "Alert",
        back_populates="camera",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Camera(id={self.id}, name={self.name}, type={self.source_type})>"
