"""
Zone Analyzer — Polygon Zone Detection.

Implements IZoneAnalyzer using supervision's PolygonZone.
Determines which tracked persons are inside defined zones
and emits ENTER/EXIT/PRESENT events based on state transitions.

Follows Single Responsibility Principle: this class ONLY handles
spatial analysis of detections against polygon zones.
"""

from __future__ import annotations

import time
from copy import deepcopy

import numpy as np
import supervision as sv

from app.core.interfaces import (
    Detection,
    IZoneAnalyzer,
    ZoneDefinition,
    ZoneEvent,
    ZoneEventType,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class _ZoneState:
    """
    Internal state for a single zone.

    Tracks which persons are currently inside and manages
    the supervision PolygonZone instance.

    Attributes:
        definition: The zone's definition (id, name, polygon, etc.).
        sv_zone: The supervision PolygonZone instance.
        current_occupants: Set of tracker IDs currently inside this zone.
    """

    __slots__ = (
        "definition",
        "sv_zone",
        "current_occupants",
        "occupant_identities",
    )

    def __init__(
        self,
        definition: ZoneDefinition,
        sv_zone: sv.PolygonZone,
    ) -> None:
        self.definition = definition
        self.sv_zone = sv_zone
        self.current_occupants: set[int] = set()
        self.occupant_identities: dict[int, tuple[str | None, float | None, str | None]] = {}


class ZoneAnalyzer(IZoneAnalyzer):
    """
    Polygon-zone-based spatial analyzer.

    For each frame, checks which tracked person detections fall inside
    the defined polygon zones (using bottom-center point / feet position).
    Compares against the previous frame's state to emit:
    - ENTER events: person was outside, now inside
    - EXIT events: person was inside, now outside
    - PRESENT events: person was inside and still is

    Args:
        zones: Initial list of zone definitions (can be empty).
        frame_shape: (height, width) of the video frame.
    """

    def __init__(
        self,
        zones: list[ZoneDefinition] | None = None,
        frame_shape: tuple[int, int] | None = None,
    ) -> None:
        self._zone_states: dict[str, _ZoneState] = {}
        self._frame_shape: tuple[int, int] | None = frame_shape

        if zones and frame_shape:
            self.update_zones(zones, frame_shape)

    def analyze(
        self,
        detections: list[Detection],
        frame: np.ndarray,
        frame_number: int,
    ) -> tuple[list[ZoneEvent], dict[str, set[int]]]:
        """
        Analyze detections against all active zones.

        Uses the bottom-center (feet) point of each detection to determine
        zone membership. Emits ENTER/EXIT/PRESENT events by comparing
        current state to the previous frame's state.

        Args:
            detections: Tracked detections with assigned IDs.
            frame: Current video frame (used for event snapshots).
            frame_number: Sequential frame number.

        Returns:
            Tuple of:
            - List of ZoneEvent objects for this frame.
            - Dict mapping zone_id → set of tracker_ids currently inside.
        """
        events: list[ZoneEvent] = []
        occupancy: dict[str, set[int]] = {}

        if not self._zone_states or not detections:
            # No zones or no detections — clear all zone occupants
            for state in self._zone_states.values():
                # Emit EXIT events for anyone who was inside
                for tracker_id in state.current_occupants:
                    events.append(
                        ZoneEvent(
                            zone_id=state.definition.zone_id,
                            zone_name=state.definition.name,
                            tracker_id=tracker_id,
                            event_type=ZoneEventType.EXIT,
                            timestamp=time.time(),
                            frame_number=frame_number,
                            snapshot=frame.copy() if frame is not None else None,
                            global_person_id=state.occupant_identities.get(
                                tracker_id, (None, None, None)
                            )[0],
                            association_confidence=state.occupant_identities.get(
                                tracker_id, (None, None, None)
                            )[1],
                            association_method=state.occupant_identities.get(
                                tracker_id, (None, None, None)
                            )[2],
                        )
                    )
                state.current_occupants.clear()
                state.occupant_identities.clear()
                occupancy[state.definition.zone_id] = set()
            return events, occupancy

        # Build supervision Detections from tracked detections
        sv_detections = self._build_sv_detections(detections)
        identities_by_tracker = {
            detection.tracker_id: (
                detection.global_person_id,
                detection.association_confidence,
                detection.association_method,
            )
            for detection in detections
            if detection.tracker_id is not None
        }

        for zone_id, state in self._zone_states.items():
            if not state.definition.is_active:
                occupancy[zone_id] = set()
                continue

            # Determine which detections are inside this zone
            in_zone_mask = state.sv_zone.trigger(sv_detections)
            current_inside: set[int] = set()

            for i, is_inside in enumerate(in_zone_mask):
                if is_inside and detections[i].tracker_id is not None:
                    current_inside.add(detections[i].tracker_id)

            previous_inside = state.current_occupants

            # Determine state transitions
            entered = current_inside - previous_inside
            exited = previous_inside - current_inside
            still_inside = current_inside & previous_inside

            # Emit ENTER events
            for tracker_id in entered:
                global_person_id, confidence, method = identities_by_tracker.get(
                    tracker_id, (None, None, None)
                )
                events.append(
                    ZoneEvent(
                        zone_id=zone_id,
                        zone_name=state.definition.name,
                        tracker_id=tracker_id,
                        event_type=ZoneEventType.ENTER,
                        timestamp=time.time(),
                        frame_number=frame_number,
                        snapshot=frame.copy(),
                        global_person_id=global_person_id,
                        association_confidence=confidence,
                        association_method=method,
                    )
                )

            # Emit EXIT events
            for tracker_id in exited:
                global_person_id, confidence, method = state.occupant_identities.get(
                    tracker_id, (None, None, None)
                )
                events.append(
                    ZoneEvent(
                        zone_id=zone_id,
                        zone_name=state.definition.name,
                        tracker_id=tracker_id,
                        event_type=ZoneEventType.EXIT,
                        timestamp=time.time(),
                        frame_number=frame_number,
                        global_person_id=global_person_id,
                        association_confidence=confidence,
                        association_method=method,
                    )
                )

            # Emit PRESENT events (less frequently — every 30 frames)
            if frame_number % 30 == 0:
                for tracker_id in still_inside:
                    global_person_id, confidence, method = identities_by_tracker.get(
                        tracker_id,
                        state.occupant_identities.get(
                            tracker_id, (None, None, None)
                        ),
                    )
                    events.append(
                        ZoneEvent(
                            zone_id=zone_id,
                            zone_name=state.definition.name,
                            tracker_id=tracker_id,
                            event_type=ZoneEventType.PRESENT,
                        timestamp=time.time(),
                        frame_number=frame_number,
                        global_person_id=global_person_id,
                        association_confidence=confidence,
                        association_method=method,
                    )
                )

            # Update state
            state.current_occupants = current_inside
            state.occupant_identities = {
                tracker_id: identities_by_tracker.get(
                    tracker_id, state.occupant_identities.get(
                        tracker_id, (None, None, None)
                    )
                )
                for tracker_id in current_inside
            }
            occupancy[zone_id] = current_inside.copy()

        return events, occupancy

    def update_zones(
        self, zones: list[ZoneDefinition], frame_shape: tuple[int, int]
    ) -> None:
        """
        Update the set of active zones.

        Converts normalized polygon coordinates (0-1) to pixel coordinates
        based on the frame dimensions. Preserves occupancy state for
        zones that haven't changed.

        Args:
            zones: List of zone definitions with normalized coordinates.
            frame_shape: (height, width) of the video frame.
        """
        self._frame_shape = frame_shape
        height, width = frame_shape

        new_states: dict[str, _ZoneState] = {}

        for zone_def in zones:
            if not zone_def.is_active:
                continue

            # Convert normalized coordinates to pixel coordinates
            pixel_polygon = np.array(
                [
                    [int(point[0] * width), int(point[1] * height)]
                    for point in zone_def.polygon
                ],
                dtype=np.int32,
            )

            sv_zone = sv.PolygonZone(
                polygon=pixel_polygon,
                triggering_anchors=[sv.Position.BOTTOM_CENTER],
            )

            # Preserve existing occupancy if zone already existed
            existing_occupants: set[int] = set()
            if zone_def.zone_id in self._zone_states:
                existing_occupants = self._zone_states[
                    zone_def.zone_id
                ].current_occupants

            state = _ZoneState(
                definition=zone_def,
                sv_zone=sv_zone,
            )
            state.current_occupants = existing_occupants
            new_states[zone_def.zone_id] = state

        self._zone_states = new_states
        logger.info(
            "Updated zones: %d active zones configured",
            len(new_states),
        )

    def get_zone_annotations(
        self, frame: np.ndarray
    ) -> np.ndarray:
        """
        Draw zone polygons on a frame for visualization.

        Args:
            frame: BGR image to annotate.

        Returns:
            Annotated frame with zone polygons drawn.
        """
        annotated = frame.copy()

        for state in self._zone_states.values():
            if not state.definition.is_active:
                continue

            # Parse hex color to BGR
            color = self._hex_to_bgr(state.definition.color)

            # Get polygon points from the supervision zone
            polygon = state.sv_zone.polygon

            # Draw filled polygon with transparency
            overlay = annotated.copy()
            cv2_polygon = polygon.reshape((-1, 1, 2))
            import cv2

            cv2.fillPoly(overlay, [cv2_polygon], color)
            cv2.addWeighted(overlay, 0.25, annotated, 0.75, 0, annotated)

            # Draw polygon border
            cv2.polylines(
                annotated, [cv2_polygon], True, color, 2
            )

            # Draw zone name
            text_pos = (polygon[0][0], polygon[0][1] - 10)
            cv2.putText(
                annotated,
                state.definition.name,
                text_pos,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )

            # Draw occupancy count
            count = len(state.current_occupants)
            count_text = f"Count: {count}"
            cv2.putText(
                annotated,
                count_text,
                (text_pos[0], text_pos[1] - 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1,
            )

        return annotated

    def _build_sv_detections(
        self, detections: list[Detection]
    ) -> sv.Detections:
        """Build a supervision Detections object from our Detection DTOs."""
        if not detections:
            return sv.Detections.empty()

        xyxy = np.array([d.bbox for d in detections], dtype=np.float32)
        confidence = np.array(
            [d.confidence for d in detections], dtype=np.float32
        )
        class_id = np.array(
            [d.class_id for d in detections], dtype=np.int32
        )
        tracker_id = np.array(
            [d.tracker_id if d.tracker_id is not None else -1 for d in detections],
            dtype=np.int32,
        )

        return sv.Detections(
            xyxy=xyxy,
            confidence=confidence,
            class_id=class_id,
            tracker_id=tracker_id,
        )

    @staticmethod
    def _hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
        """Convert hex color string to BGR tuple for OpenCV."""
        hex_color = hex_color.lstrip("#")
        r, g, b = (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )
        return (b, g, r)
