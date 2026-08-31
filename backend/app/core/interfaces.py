"""
Core Interfaces (Abstract Base Classes).

Defines the contracts that all core engine components must implement.
This is the foundation of the Dependency Inversion Principle — high-level
modules (Pipeline, Services) depend on these abstractions, not on concrete
implementations.

These interfaces enable:
- Swapping YOLO for any other detector
- Swapping ByteTrack for any other tracker
- Adding new video source types without modifying existing code
- Easy mocking for unit tests
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Data Transfer Objects (used across interfaces)
# ---------------------------------------------------------------------------

class ZoneEventType(Enum):
    """Types of zone crossing events."""

    ENTER = "ENTER"
    EXIT = "EXIT"
    PRESENT = "PRESENT"


@dataclass
class Detection:
    """
    A single detection result.

    Attributes:
        bbox: Bounding box as [x1, y1, x2, y2] in pixel coordinates.
        confidence: Detection confidence score (0.0 to 1.0).
        class_id: Detected class ID (0 = person in COCO).
        tracker_id: Assigned tracking ID (None if not yet tracked).
        global_person_id: Anonymous identity shared by associated camera tracks.
    """

    bbox: np.ndarray  # shape: (4,) — [x1, y1, x2, y2]
    confidence: float
    class_id: int
    tracker_id: int | None = None
    global_person_id: str | None = None
    association_confidence: float | None = None
    association_method: str | None = None

    @property
    def center(self) -> tuple[float, float]:
        """Center point of the bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def bottom_center(self) -> tuple[float, float]:
        """Bottom-center point (feet position) of the bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, y2)


@dataclass
class DetectionResult:
    """
    Result from a detection + tracking pass on a single frame.

    Attributes:
        detections: List of individual detections with tracking IDs.
        frame: The original frame that was processed.
        annotated_frame: Frame with visual annotations (bboxes, labels).
        frame_number: Sequential frame count.
    """

    detections: list[Detection]
    frame: np.ndarray
    annotated_frame: np.ndarray | None = None
    frame_number: int = 0


@dataclass
class ZoneEvent:
    """
    An event triggered when a tracked person interacts with a zone.

    Attributes:
        zone_id: Database ID of the zone.
        zone_name: Human-readable zone name.
        tracker_id: Tracking ID of the person.
        event_type: Type of event (ENTER, EXIT, PRESENT).
        timestamp: Unix timestamp of the event.
        frame_number: Frame number when the event occurred.
        snapshot: Captured frame at the time of the event.
    """

    zone_id: str
    zone_name: str
    tracker_id: int
    event_type: ZoneEventType
    timestamp: float
    frame_number: int
    snapshot: np.ndarray | None = None
    global_person_id: str | None = None
    association_confidence: float | None = None
    association_method: str | None = None


@dataclass
class ZoneDefinition:
    """
    Definition of a detection zone.

    Attributes:
        zone_id: Unique identifier for the zone.
        name: Human-readable zone name.
        polygon: Polygon vertices as normalized coordinates (0-1).
        color: Display color as hex string.
        is_active: Whether the zone is currently active.
    """

    zone_id: str
    name: str
    polygon: list[list[float]]  # [[x1,y1], [x2,y2], ...] normalized 0-1
    color: str = "#FF0000"
    is_active: bool = True


@dataclass
class PipelineResult:
    """
    Complete result from one pipeline processing cycle.

    Attributes:
        detection_result: The raw detection + tracking result.
        zone_events: List of zone events triggered in this frame.
        active_zone_occupancy: Mapping of zone_id → set of tracker_ids currently inside.
    """

    detection_result: DetectionResult
    zone_events: list[ZoneEvent] = field(default_factory=list)
    active_zone_occupancy: dict[str, set[int]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract Interfaces
# ---------------------------------------------------------------------------

class IDetector(ABC):
    """
    Contract for object detection implementations.

    Any detector (YOLO, SSD, EfficientDet, etc.) can be plugged in
    by implementing this interface.
    """

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[Detection]:
        """
        Run detection on a single frame.

        Args:
            frame: BGR image as numpy array (H, W, 3).

        Returns:
            List of Detection objects found in the frame.
        """
        ...

    @abstractmethod
    def warmup(self) -> None:
        """
        Perform a warmup inference to initialize the model.

        Should be called once before the first real detection
        to avoid cold-start latency.
        """
        ...


class ITracker(ABC):
    """
    Contract for multi-object tracking implementations.

    Any tracker (ByteTrack, DeepSORT, BoT-SORT, etc.) can be plugged in
    by implementing this interface.
    """

    @abstractmethod
    def update(self, detections: list[Detection], frame: np.ndarray) -> list[Detection]:
        """
        Update tracker state with new detections and return tracked detections.

        Args:
            detections: List of detections from the current frame.
            frame: The current video frame (used by some trackers for re-ID).

        Returns:
            List of Detection objects with tracker_id assigned.
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset the tracker state, clearing all active tracks."""
        ...


class IZoneAnalyzer(ABC):
    """
    Contract for spatial zone analysis implementations.

    Responsible for determining which tracked persons are inside
    which defined zones and emitting appropriate events.
    """

    @abstractmethod
    def analyze(
        self,
        detections: list[Detection],
        frame: np.ndarray,
        frame_number: int,
    ) -> tuple[list[ZoneEvent], dict[str, set[int]]]:
        """
        Analyze detections against defined zones.

        Args:
            detections: Tracked detections with assigned IDs.
            frame: Current video frame (for snapshots).
            frame_number: Sequential frame number.

        Returns:
            Tuple of:
            - List of ZoneEvent objects (ENTER/EXIT/PRESENT events).
            - Dict mapping zone_id → set of tracker_ids currently inside.
        """
        ...

    @abstractmethod
    def update_zones(self, zones: list[ZoneDefinition], frame_shape: tuple[int, int]) -> None:
        """
        Update the set of active zones.

        Called when zones are added, removed, or modified via the dashboard.

        Args:
            zones: List of zone definitions.
            frame_shape: (height, width) of the video frame for denormalization.
        """
        ...


class IVideoSource(ABC):
    """
    Contract for video input sources.

    Abstracts away the differences between webcams, RTSP streams,
    and video files.
    """

    @abstractmethod
    def open(self) -> None:
        """Open the video source and prepare for reading frames."""
        ...

    @abstractmethod
    def read(self) -> tuple[bool, np.ndarray | None]:
        """
        Read the next frame from the source.

        Returns:
            Tuple of (success: bool, frame: ndarray or None).
        """
        ...

    @abstractmethod
    def release(self) -> None:
        """Release the video source and free resources."""
        ...

    @abstractmethod
    def is_opened(self) -> bool:
        """Check if the video source is currently open."""
        ...

    @property
    @abstractmethod
    def frame_width(self) -> int:
        """Width of the video frames in pixels."""
        ...

    @property
    @abstractmethod
    def frame_height(self) -> int:
        """Height of the video frames in pixels."""
        ...

    @property
    @abstractmethod
    def fps(self) -> float:
        """Frames per second of the video source."""
        ...

    @property
    @abstractmethod
    def source_uri(self) -> str:
        """The URI/path of the video source."""
        ...


class IFrameCallback(ABC):
    """
    Contract for pipeline frame callbacks.

    Used to notify external systems (e.g., SocketIO broadcaster)
    when a new processed frame is available.
    """

    @abstractmethod
    def on_frame_processed(self, result: PipelineResult) -> None:
        """
        Called when the pipeline finishes processing a frame.

        Args:
            result: The complete pipeline result for the frame.
        """
        ...

    @abstractmethod
    def on_pipeline_error(self, error: Exception) -> None:
        """
        Called when the pipeline encounters an error.

        Args:
            error: The exception that occurred.
        """
        ...

    @abstractmethod
    def on_pipeline_stopped(self) -> None:
        """Called when the pipeline stops (gracefully or due to source exhaustion)."""
        ...
