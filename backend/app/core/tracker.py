"""
Person Tracker — ByteTrack Wrapper.

Implements ITracker using the supervision library's ByteTrack implementation.
Assigns persistent tracking IDs to detections across frames.

Follows Single Responsibility Principle: this class ONLY handles
maintaining track identity across frames.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import supervision as sv

from app.config import TrackerConfig
from app.core.interfaces import Detection, ITracker
from app.utils.exceptions import TrackerError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PersonTracker(ITracker):
    """
    ByteTrack-based multi-object tracker.

    Wraps the supervision library's ByteTrack to assign persistent
    tracking IDs to person detections across video frames.

    Key features:
    - Handles occlusion recovery via ByteTrack's low-confidence matching
    - Maintains consistent IDs even during brief disappearances
    - Configurable lost track buffer for tuning re-identification

    Args:
        config: Tracker configuration.
    """

    def __init__(self, config: TrackerConfig) -> None:
        self._config = config
        self._tracker: sv.ByteTrack | None = None
        self._initialize_tracker()

    def _initialize_tracker(self) -> None:
        """Initialize the ByteTrack tracker with configured parameters."""
        try:
            self._tracker = sv.ByteTrack(
                track_activation_threshold=self._config.track_activation_threshold,
                lost_track_buffer=self._config.lost_track_buffer,
                minimum_matching_threshold=self._config.minimum_matching_threshold,
                frame_rate=self._config.frame_rate,
            )
            logger.info("ByteTrack tracker initialized")
        except Exception as e:
            raise TrackerError(f"Failed to initialize ByteTrack: {e}") from e

    def update(
        self, detections: list[Detection], frame: np.ndarray
    ) -> list[Detection]:
        """
        Update tracker with new detections and return tracked results.

        Converts our Detection DTOs to supervision format, runs ByteTrack
        update, then converts back to Detection DTOs with assigned tracker IDs.

        Args:
            detections: Raw detections from the current frame.
            frame: Current video frame (not used by ByteTrack but part of interface).

        Returns:
            List of Detection objects with tracker_id assigned.

        Raises:
            TrackerError: If tracking update fails.
        """
        if self._tracker is None:
            raise TrackerError("Tracker not initialized")

        try:
            # Convert to supervision Detections format
            sv_detections = self._to_supervision_detections(detections)

            # Run ByteTrack update
            tracked = self._tracker.update_with_detections(sv_detections)

            # Convert back to our Detection DTOs
            return self._from_supervision_detections(tracked)

        except Exception as e:
            raise TrackerError(f"Tracking update failed: {e}") from e

    def reset(self) -> None:
        """Reset tracker state, clearing all active tracks."""
        logger.info("Resetting tracker state")
        self._initialize_tracker()

    def set_frame_rate(self, frame_rate: float) -> None:
        """Align the lost-track duration with the active video source FPS."""
        if frame_rate <= 0 or self._config.frame_rate == frame_rate:
            return
        self._config = replace(self._config, frame_rate=frame_rate)
        self._initialize_tracker()

    def _to_supervision_detections(
        self, detections: list[Detection]
    ) -> sv.Detections:
        """
        Convert our Detection DTOs to supervision's Detections format.

        Args:
            detections: List of our Detection objects.

        Returns:
            supervision.Detections object.
        """
        if not detections:
            return sv.Detections.empty()

        xyxy = np.array([d.bbox for d in detections], dtype=np.float32)
        confidence = np.array(
            [d.confidence for d in detections], dtype=np.float32
        )
        class_id = np.array(
            [d.class_id for d in detections], dtype=np.int32
        )

        return sv.Detections(
            xyxy=xyxy,
            confidence=confidence,
            class_id=class_id,
        )

    def _from_supervision_detections(
        self, sv_detections: sv.Detections
    ) -> list[Detection]:
        """
        Convert supervision's Detections back to our Detection DTOs.

        Args:
            sv_detections: supervision.Detections with tracker IDs.

        Returns:
            List of Detection objects with tracker_id set.
        """
        detections: list[Detection] = []

        if len(sv_detections) == 0:
            return detections

        for i in range(len(sv_detections)):
            tracker_id = None
            if sv_detections.tracker_id is not None:
                tracker_id = int(sv_detections.tracker_id[i])

            confidence = 0.0
            if sv_detections.confidence is not None:
                confidence = float(sv_detections.confidence[i])

            class_id = 0
            if sv_detections.class_id is not None:
                class_id = int(sv_detections.class_id[i])

            detections.append(
                Detection(
                    bbox=sv_detections.xyxy[i].astype(np.float32),
                    confidence=confidence,
                    class_id=class_id,
                    tracker_id=tracker_id,
                )
            )

        return detections
