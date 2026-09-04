"""
Detection Service.

Manages DetectionPipeline instances per camera. Orchestrates
pipeline lifecycle (start/stop), broadcasts results via SocketIO,
and bridges the core engine with the service layer.
"""

from __future__ import annotations

import base64
import threading
from typing import TYPE_CHECKING

import cv2
import numpy as np

from app.config import AppConfig
from app.core.detector import PersonDetector
from app.core.global_identity import GlobalIdentityService
from app.core.interfaces import (
    IFrameCallback,
    PipelineResult,
    ZoneDefinition,
)
from app.core.pipeline import DetectionPipeline, PipelineStatus
from app.core.reid import PersonReIdentifier
from app.core.tracker import PersonTracker
from app.core.video_source import VideoSourceFactory
from app.core.zone_analyzer import ZoneAnalyzer
from app.core.interfaces import ZoneEventType
from app.services.incident_clip_recorder import IncidentClipRecorder
from app.utils.exceptions import (
    PipelineAlreadyRunningError,
    PipelineNotRunningError,
)
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from flask_socketio import SocketIO

logger = get_logger(__name__)


class _SocketIOCallback(IFrameCallback):
    """
    Callback that broadcasts pipeline results via Flask-SocketIO.

    Encodes annotated frames as base64 JPEG and emits them
    along with zone events to connected clients.
    """

    def __init__(
        self,
        camera_id: str,
        socketio: SocketIO,
        frame_quality: int = 70,
        alert_service=None,
        app=None,
        clips_dir=None,
    ) -> None:
        self._camera_id = camera_id
        self._socketio = socketio
        self._frame_quality = frame_quality
        self._alert_service = alert_service
        self._app = app
        self._clip_recorder = IncidentClipRecorder(
            camera_id, clips_dir, 30, self._save_clip_path
        ) if clips_dir is not None else None

    def _save_clip_path(self, alert_id: str, clip_path: str) -> None:
        if self._alert_service is None or self._app is None:
            return
        with self._app.app_context():
            self._alert_service.set_clip_path(alert_id, clip_path)

    def on_frame_processed(self, result: PipelineResult) -> None:
        """Broadcast annotated frame and zone events."""
        if self._clip_recorder is not None:
            self._clip_recorder.capture(result.detection_result.annotated_frame)
        # Encode frame as JPEG
        frame_data = None
        if result.detection_result.annotated_frame is not None:
            _, buffer = cv2.imencode(
                ".jpg",
                result.detection_result.annotated_frame,
                [cv2.IMWRITE_JPEG_QUALITY, self._frame_quality],
            )
            frame_data = base64.b64encode(buffer).decode("utf-8")

        # Emit frame to camera-specific room
        self._socketio.emit(
            "frame",
            {
                "camera_id": self._camera_id,
                "frame": frame_data,
                "frame_number": result.detection_result.frame_number,
                "detections_count": len(result.detection_result.detections),
                "detections": [
                    {
                        "tracker_id": detection.tracker_id,
                        "global_person_id": detection.global_person_id,
                        "association_confidence": detection.association_confidence,
                        "association_method": detection.association_method,
                        "bbox": detection.bbox.tolist(),
                        "confidence": detection.confidence,
                    }
                    for detection in result.detection_result.detections
                ],
                "occupancy": {
                    zid: list(tids)
                    for zid, tids in result.active_zone_occupancy.items()
                },
            },
            namespace="/stream",
            room=f"camera_{self._camera_id}",
        )

        # Process zone events
        for event in result.zone_events:
            # Emit real-time alert
            self._socketio.emit(
                "zone_alert",
                {
                    "camera_id": self._camera_id,
                    "zone_id": event.zone_id,
                    "zone_name": event.zone_name,
                    "tracker_id": event.tracker_id,
                    "global_person_id": event.global_person_id,
                    "association_confidence": event.association_confidence,
                    "association_method": event.association_method,
                    "event_type": event.event_type.value,
                    "timestamp": event.timestamp,
                    "frame_number": event.frame_number,
                },
                namespace="/alerts",
            )

            # Persist to database within application context
            if self._alert_service is not None and self._app is not None:
                try:
                    with self._app.app_context():
                        alert = self._alert_service.process_zone_event(
                            event, self._camera_id
                        )
                        if (
                            alert is not None
                            and self._clip_recorder is not None
                            and event.event_type != ZoneEventType.EXIT
                        ):
                            self._clip_recorder.start_incident(alert.id, event.timestamp)
                except Exception as e:
                    logger.error("Failed to persist alert: %s", e)

    def on_pipeline_error(self, error: Exception) -> None:
        """Notify clients of pipeline error."""
        self._socketio.emit(
            "camera_status",
            {
                "camera_id": self._camera_id,
                "status": "ERROR",
                "error": str(error),
            },
            namespace="/stream",
        )

    def on_pipeline_stopped(self) -> None:
        """Notify clients that pipeline stopped."""
        self._socketio.emit(
            "camera_status",
            {
                "camera_id": self._camera_id,
                "status": "STOPPED",
            },
            namespace="/stream",
        )


class DetectionServiceManager:
    """
    Manages detection pipelines for all cameras.

    Singleton-like manager that creates, starts, stops, and tracks
    pipeline instances. One pipeline per camera.
    """

    def __init__(self, config: AppConfig, socketio: SocketIO = None, app=None) -> None:
        if not config.reid.enabled:
            raise RuntimeError("OSNet ReID is required for cross-camera identity tracking")
        self._config = config
        self._socketio = socketio
        self._app = app
        self._pipelines: dict[str, DetectionPipeline] = {}
        self._detector: PersonDetector | None = None
        self._global_identity_service = GlobalIdentityService(
            config.global_identity,
            reid_similarity_threshold=config.reid.similarity_threshold,
            require_reid=config.reid.enabled,
        )
        self._reidentifier = PersonReIdentifier(config.reid)
        self._lock = threading.Lock()

    def _get_or_create_detector(self) -> PersonDetector:
        """
        Get or lazily create the shared YOLO detector.

        The detector is shared across pipelines to avoid loading
        multiple copies of the model into GPU memory.
        """
        if self._detector is None:
            self._detector = PersonDetector(self._config.detection)
        return self._detector

    def start_pipeline(
        self,
        camera_id: str,
        source_uri: str,
        source_type: str,
        zones: list[ZoneDefinition] | None = None,
        alert_service=None,
        overlap_group: str | None = None,
        ground_plane_homography: list[list[float]] | None = None,
    ) -> None:
        """
        Start a detection pipeline for a camera.

        Args:
            camera_id: Camera ID.
            source_uri: Video source URI.
            source_type: Source type (file, rtsp, webcam).
            zones: Initial zone definitions.
            alert_service: Alert service for persisting events.

        Raises:
            PipelineAlreadyRunningError: If pipeline is already running.
        """
        with self._lock:
            if camera_id in self._pipelines:
                existing = self._pipelines[camera_id]
                if existing.status == PipelineStatus.RUNNING:
                    raise PipelineAlreadyRunningError(camera_id)

            # Create components
            detector = self._get_or_create_detector()
            tracker = PersonTracker(self._config.tracker)
            zone_analyzer = ZoneAnalyzer()
            self._global_identity_service.clear_camera(camera_id)
            self._global_identity_service.configure_camera(
                camera_id,
                overlap_group,
                ground_plane_homography,
            )
            video_source = VideoSourceFactory.create(
                source_uri, source_type=source_type, loop=True
            )

            # Create callback
            callback = None
            if self._socketio is not None:
                callback = _SocketIOCallback(
                    camera_id=camera_id,
                    socketio=self._socketio,
                    frame_quality=self._config.stream.frame_quality,
                    alert_service=alert_service,
                    app=self._app,
                    clips_dir=self._config.clips_dir,
                )

            # Create pipeline
            pipeline = DetectionPipeline(
                camera_id=camera_id,
                detector=detector,
                tracker=tracker,
                zone_analyzer=zone_analyzer,
                video_source=video_source,
                stream_config=self._config.stream,
                callback=callback,
                identity_service=self._global_identity_service,
                reidentifier=self._reidentifier,
            )

            # Set up zones if provided
            if zones:
                # Need to get frame dimensions first
                video_source.open()
                frame_shape = (
                    video_source.frame_height,
                    video_source.frame_width,
                )
                video_source.release()

                zone_analyzer.update_zones(zones, frame_shape)

                # Recreate video source since we consumed it
                video_source = VideoSourceFactory.create(
                    source_uri, source_type=source_type, loop=True
                )
                pipeline._video_source = video_source

            self._pipelines[camera_id] = pipeline

        # Start outside lock
        pipeline.start()

        # Notify clients
        if self._socketio is not None:
            self._socketio.emit(
                "camera_status",
                {"camera_id": camera_id, "status": "RUNNING"},
                namespace="/stream",
            )

        logger.info("Pipeline started for camera '%s'", camera_id)

    def stop_pipeline(self, camera_id: str) -> None:
        """
        Stop a detection pipeline.

        Raises:
            PipelineNotRunningError: If no pipeline is running for this camera.
        """
        with self._lock:
            if camera_id not in self._pipelines:
                raise PipelineNotRunningError(camera_id)

            pipeline = self._pipelines[camera_id]

        pipeline.stop()

        with self._lock:
            del self._pipelines[camera_id]
            self._global_identity_service.clear_camera(camera_id)

        logger.info("Pipeline stopped for camera '%s'", camera_id)

    def update_zones(
        self, camera_id: str, zones: list[ZoneDefinition]
    ) -> None:
        """
        Hot-reload zones for a running pipeline.

        Args:
            camera_id: Camera to update zones for.
            zones: New zone definitions.
        """
        with self._lock:
            if camera_id in self._pipelines:
                self._pipelines[camera_id].update_zones(zones)
                logger.info(
                    "Zones hot-reloaded for camera '%s': %d zones",
                    camera_id,
                    len(zones),
                )

    def get_pipeline_status(self, camera_id: str) -> str:
        """Get the status of a camera's pipeline."""
        with self._lock:
            if camera_id in self._pipelines:
                return self._pipelines[camera_id].status.value
        return PipelineStatus.IDLE.value

    def get_all_statuses(self) -> dict[str, str]:
        """Get statuses for all pipelines."""
        with self._lock:
            return {
                cid: p.status.value for cid, p in self._pipelines.items()
            }

    def stop_all(self) -> None:
        """Stop all running pipelines (for graceful shutdown)."""
        with self._lock:
            camera_ids = list(self._pipelines.keys())

        for camera_id in camera_ids:
            try:
                self.stop_pipeline(camera_id)
            except Exception as e:
                logger.error(
                    "Error stopping pipeline for camera '%s': %s",
                    camera_id,
                    e,
                )
