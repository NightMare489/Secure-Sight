"""
Alert ORM Model.

Represents a zone intrusion event. Created when a tracked person
enters a detection zone. Stores the event details and optionally
a snapshot image path.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin


class Alert(Base, UUIDMixin):
    """
    Alert entity.

    Attributes:
        id: UUID primary key.
        zone_id: Foreign key to the zone that triggered the alert.
        camera_id: Foreign key to the camera.
        tracker_id: Person's tracking ID.
        event_type: Type of event ("ENTER", "EXIT", "PRESENT").
        timestamp: When the event occurred (UTC datetime).
        snapshot_path: Path to the captured frame image (optional).
        metadata_json: Extensible JSON metadata field.
    """

    __tablename__ = "alerts"

    zone_id = Column(
        String(36),
        ForeignKey("zones.id", ondelete="CASCADE"),
        nullable=False,
    )
    camera_id = Column(
        String(36),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
    )
    tracker_id = Column(Integer, nullable=False)
    global_person_id = Column(String(36), nullable=True, index=True)
    association_confidence = Column(Float, nullable=True)
    association_method = Column(String(30), nullable=True)
    event_type = Column(String(20), nullable=False)  # ENTER, EXIT, PRESENT
    timestamp = Column(DateTime, nullable=False)
    snapshot_path = Column(String(500), nullable=True)
    metadata_json = Column(Text, nullable=True, default="{}")

    # Relationships
    zone = relationship("Zone", back_populates="alerts")
    camera = relationship("Camera", back_populates="alerts")

    def __repr__(self) -> str:
        return (
            f"<Alert(id={self.id}, type={self.event_type}, "
            f"zone_id={self.zone_id}, tracker_id={self.tracker_id})>"
        )
