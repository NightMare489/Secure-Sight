"""
Detection Pipeline — Orchestrator.

Composes IDetector, ITracker, and IZoneAnalyzer into a single
processing pipeline that runs the full detection cycle per frame:

    Frame → Detect → Track → Analyze Zones → Annotate → Emit Events

Follows Single Responsibility Principle: this class ONLY orchestrates
the flow between components — it does NOT implement any detection,
tracking, or zone logic.

Follows Open/Closed Principle: new processing steps can be added
(e.g., face blur, heatmap generation) by extending callbacks,
not by modifying this class.
"""

from __future__ import annotations

import threading
import time
from enum import Enum

import cv2
import numpy as np

from app.config import StreamConfig
from app.core.global_identity import GlobalIdentityService
from app.core.reid import PersonReIdentifier
from app.core.interfaces import (
    Detection,
    DetectionResult,
    IDetector,
    IFrameCallback,
    ITracker,
    IVideoSource,
    IZoneAnalyzer,
    PipelineResult,
    ZoneDefinition,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PipelineStatus(Enum):
    """Pipeline lifecycle states."""

    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class DetectionPipeline:
    """
    Orchestrates the full detection → tracking → zone analysis cycle.

    Runs in a separate thread, processing frames from a video source
    and notifying callbacks with results. Designed for one pipeline
    per camera.

    Args:
        camera_id: Unique identifier for the camera this pipeline serves.
        detector: Person detector implementation.
        tracker: Multi-object tracker implementation.
        zone_analyzer: Zone analysis implementation.
        video_source: Video input source.
        stream_config: Streaming configuration (FPS, quality, etc.).
        callback: Optional callback for frame results.
    """

    def __init__(
        self,
        camera_id: str,
        detector: IDetector,
        tracker: ITracker,
        zone_analyzer: IZoneAnalyzer,
        video_source: IVideoSource,
        stream_config: StreamConfig | None = None,
        callback: IFrameCallback | None = None,
        identity_service: GlobalIdentityService | None = None,
        reidentifier: PersonReIdentifier | None = None,
    ) -> None:
        self._camera_id = camera_id
        self._detector = detector
        self._tracker = tracker
        self._zone_analyzer = zone_analyzer
        self._video_source = video_source
        self._stream_config = stream_config or StreamConfig()
        self._callback = callback
        self._identity_service = identity_service
        self._reidentifier = reidentifier

        self._status = PipelineStatus.IDLE
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._frame_count = 0
        self._lock = threading.Lock()

        # Annotation tools
        self._box_annotator = None
        self._label_annotator = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def status(self) -> PipelineStatus:
        """Current pipeline status."""
        return self._status

    @property
    def camera_id(self) -> str:
        """Camera ID this pipeline is associated with."""
        return self._camera_id

    @property
    def frame_count(self) -> int:
        """Total frames processed since pipeline start."""
        return self._frame_count

    def start(self) -> None:
        """
        Start the detection pipeline in a background thread.

        Raises:
            RuntimeError: If the pipeline is already running.
        """
        with self._lock:
            if self._status == PipelineStatus.RUNNING:
                logger.warning(
                    "Pipeline for camera '%s' is already running",
                    self._camera_id,
                )
                return

            self._status = PipelineStatus.STARTING
            self._stop_event.clear()
            self._frame_count = 0

        self._thread = threading.Thread(
            target=self._run,
            name=f"pipeline-{self._camera_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info("Pipeline started for camera '%s'", self._camera_id)

    def stop(self) -> None:
        """
        Stop the detection pipeline gracefully.

        Signals the processing thread to stop and waits for it to finish.
        """
        with self._lock:
            if self._status not in (
                PipelineStatus.RUNNING,
                PipelineStatus.STARTING,
            ):
                logger.warning(
                    "Pipeline for camera '%s' is not running (status: %s)",
                    self._camera_id,
                    self._status.value,
                )
                return

            self._status = PipelineStatus.STOPPING

        logger.info("Stopping pipeline for camera '%s'...", self._camera_id)
        self._stop_event.set()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10.0)

        self._status = PipelineStatus.STOPPED
        logger.info("Pipeline stopped for camera '%s'", self._camera_id)

    def update_zones(self, zones: list[ZoneDefinition]) -> None:
        """
        Hot-reload zone definitions while the pipeline is running.

        Thread-safe — can be called from the API thread.

        Args:
            zones: Updated list of zone definitions.
        """
        if self._video_source.is_opened():
            frame_shape = (
                self._video_source.frame_height,
                self._video_source.frame_width,
            )
            self._zone_analyzer.update_zones(zones, frame_shape)
            logger.info(
                "Zones updated for camera '%s': %d zones",
                self._camera_id,
                len(zones),
            )

    def set_callback(self, callback: IFrameCallback) -> None:
        """Set or replace the frame callback."""
        self._callback = callback

    # ------------------------------------------------------------------
    # Internal Processing Loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """
        Main processing loop — runs in a background thread.

        Reads frames, runs detection → tracking → zone analysis,
        annotates the frame, and notifies callbacks.
        """
        try:
            # Open video source
            self._video_source.open()
            self._status = PipelineStatus.RUNNING

            # ByteTrack normalizes its lost-track buffer at 30 FPS. Set the
            # actual source rate before processing any frames so a configured
            # duration means the same thing for files, RTSP, and webcams.
            set_frame_rate = getattr(self._tracker, "set_frame_rate", None)
            if callable(set_frame_rate):
                set_frame_rate(self._video_source.fps)

            # Warmup detector
            self._detector.warmup()

            # Initialize annotation tools
            self._init_annotators()

            # Calculate frame delay for target FPS
            target_fps = min(
                self._stream_config.max_fps, self._video_source.fps
            )
            frame_delay = 1.0 / target_fps if target_fps > 0 else 0.033

            logger.info(
                "Pipeline running for camera '%s' at %.1f FPS",
                self._camera_id,
                target_fps,
            )

            while not self._stop_event.is_set():
                loop_start = time.time()

                # 1. Read frame
                success, frame = self._video_source.read()
                if not success or frame is None:
                    logger.info(
                        "Video source exhausted for camera '%s'",
                        self._camera_id,
                    )
                    break

                self._frame_count += 1

                # 2. Process frame
                result = self._process_frame(frame, self._frame_count)

                # 3. Notify callback
                if self._callback is not None:
                    try:
                        self._callback.on_frame_processed(result)
                    except Exception as cb_error:
                        logger.error(
                            "Callback error: %s", cb_error, exc_info=True
                        )

                # 4. Frame rate limiting
                elapsed = time.time() - loop_start
                sleep_time = frame_delay - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except Exception as e:
            self._status = PipelineStatus.ERROR
            logger.error(
                "Pipeline error for camera '%s': %s",
                self._camera_id,
                e,
                exc_info=True,
            )
            if self._callback is not None:
                self._callback.on_pipeline_error(e)
        finally:
            self._video_source.release()
            self._tracker.reset()

            if self._status != PipelineStatus.ERROR:
                self._status = PipelineStatus.STOPPED

            if self._callback is not None:
                self._callback.on_pipeline_stopped()

            logger.info(
                "Pipeline thread exiting for camera '%s' (processed %d frames)",
                self._camera_id,
                self._frame_count,
            )

    def _process_frame(
        self, frame: np.ndarray, frame_number: int
    ) -> PipelineResult:
        """
        Run the full detection cycle on a single frame.

        Args:
            frame: BGR image from the video source.
            frame_number: Sequential frame number.

        Returns:
            Complete PipelineResult with detections, events, and annotations.
        """
        # Step 1: Detect persons
        detections = self._detector.detect(frame)

        # Step 2: Track across frames
        tracked_detections = self._tracker.update(detections, frame)

        # Step 3: Associate the camera-local tracks with anonymous global IDs.
        # Zone occupancy remains keyed by the local tracker ID.
        if self._identity_service is not None:
            embeddings = (
                self._reidentifier.encode(frame, tracked_detections, frame_number)
                if self._reidentifier is not None
                else None
            )
            tracked_detections = self._identity_service.resolve(
                self._camera_id,
                tracked_detections,
                timestamp=time.time(),
                embeddings=embeddings,
            )

        # Step 4: Analyze zone interactions
        zone_events, occupancy = self._zone_analyzer.analyze(
            tracked_detections, frame, frame_number
        )

        # Step 5: Annotate frame
        annotated_frame = self._annotate_frame(
            frame, tracked_detections
        )

        # Step 6: Draw zone overlays
        annotated_frame = self._zone_analyzer.get_zone_annotations(
            annotated_frame
        )

        # Build result
        detection_result = DetectionResult(
            detections=tracked_detections,
            frame=frame,
            annotated_frame=annotated_frame,
            frame_number=frame_number,
        )

        return PipelineResult(
            detection_result=detection_result,
            zone_events=zone_events,
            active_zone_occupancy=occupancy,
        )

    def _annotate_frame(
        self, frame: np.ndarray, detections: list[Detection]
    ) -> np.ndarray:
        """
        Draw bounding boxes and labels on the frame.

        Args:
            frame: BGR image.
            detections: Tracked detections.

        Returns:
            Annotated frame.
        """
        annotated = frame.copy()

        for det in detections:
            if det.tracker_id is None:
                continue

            x1, y1, x2, y2 = det.bbox.astype(int)

            # Draw bounding box
            color = (0, 255, 0)  # Green for tracked persons
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Draw label
            global_label = (
                f" G:{det.global_person_id[:8]}"
                if det.global_person_id is not None
                else ""
            )
            label = f"ID:{det.tracker_id}{global_label} ({det.confidence:.0%})"
            label_size, _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            label_width, label_height = label_size
            frame_height, frame_width = annotated.shape[:2]

            # Keep labels inside the visible image. For people at the top
            # edge, draw the banner inside the box instead of above it.
            label_x = min(max(0, x1), max(0, frame_width - label_width - 2))
            if y1 >= label_height + 10:
                label_top = y1 - label_height - 10
            elif y2 + label_height + 10 < frame_height:
                label_top = y2 + 2
            else:
                label_top = min(
                    max(0, y1), max(0, frame_height - label_height - 10)
                )
            label_bottom = label_top + label_height + 10
            label_baseline = label_top + label_height + 5

            # Label background
            cv2.rectangle(
                annotated,
                (label_x, label_top),
                (label_x + label_width, label_bottom),
                color,
                -1,
            )

            # Label text
            cv2.putText(
                annotated,
                label,
                (label_x, label_baseline),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1,
            )

        return annotated

    def _init_annotators(self) -> None:
        """Initialize supervision annotation tools (reserved for future use)."""
        try:
            import supervision as sv
            self._box_annotator = sv.BoxAnnotator(thickness=2)
            self._label_annotator = sv.LabelAnnotator(text_scale=0.5)
        except ImportError:
            logger.warning(
                "supervision not available — using basic OpenCV annotations"
            )
