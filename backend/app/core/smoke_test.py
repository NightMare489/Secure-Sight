"""
CLI Smoke Test for the Core Detection Engine.

Usage:
    python -m app.core.smoke_test --video path/to/video.mp4

This script runs the full detection pipeline on a video file
and displays the annotated output in a window. Use it to verify
that the core engine is working correctly before integrating
with the web layer.
"""

from __future__ import annotations

import argparse
import sys
import time

import cv2

from app.config import AppConfig
from app.core.detector import PersonDetector
from app.core.interfaces import (
    IFrameCallback,
    PipelineResult,
    ZoneDefinition,
)
from app.core.pipeline import DetectionPipeline
from app.core.tracker import PersonTracker
from app.core.video_source import VideoSourceFactory
from app.core.zone_analyzer import ZoneAnalyzer
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CLIDisplayCallback(IFrameCallback):
    """Display frames in an OpenCV window and print zone events."""

    def __init__(self) -> None:
        self.latest_frame = None
        self.running = True

    def on_frame_processed(self, result: PipelineResult) -> None:
        """Display the annotated frame."""
        if result.detection_result.annotated_frame is not None:
            self.latest_frame = result.detection_result.annotated_frame

        # Log zone events
        for event in result.zone_events:
            logger.info(
                "ZONE EVENT: %s | Zone: %s | Person ID: %d | Frame: %d",
                event.event_type.value,
                event.zone_name,
                event.tracker_id,
                event.frame_number,
            )

    def on_pipeline_error(self, error: Exception) -> None:
        logger.error("Pipeline error: %s", error)
        self.running = False

    def on_pipeline_stopped(self) -> None:
        logger.info("Pipeline stopped")
        self.running = False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Secure Sight Core Engine Smoke Test"
    )
    parser.add_argument(
        "--video",
        type=str,
        required=True,
        help="Path to a video file for testing",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Loop the video file",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        help="Inference device: 'cuda' or 'cpu' (default: cuda)",
    )
    args = parser.parse_args()

    # Load config
    config = AppConfig.from_env()

    # Override device if specified
    if args.device:
        from app.config import DetectionConfig

        detection_config = DetectionConfig(
            model_path=config.detection.model_path,
            confidence_threshold=config.detection.confidence_threshold,
            person_class_id=config.detection.person_class_id,
            device=args.device,
            img_size=config.detection.img_size,
        )
    else:
        detection_config = config.detection

    # Create components
    logger.info("Initializing core engine components...")

    detector = PersonDetector(detection_config)
    tracker = PersonTracker(config.tracker)
    zone_analyzer = ZoneAnalyzer()
    video_source = VideoSourceFactory.create(
        args.video, source_type="file", loop=args.loop
    )

    # Create callback
    callback = CLIDisplayCallback()

    # Create pipeline
    pipeline = DetectionPipeline(
        camera_id="smoke-test",
        detector=detector,
        tracker=tracker,
        zone_analyzer=zone_analyzer,
        video_source=video_source,
        stream_config=config.stream,
        callback=callback,
    )

    # Open video source temporarily to get frame dimensions for zones
    video_source.open()
    frame_shape = (video_source.frame_height, video_source.frame_width)
    video_source.release()

    # Set up a demo zone (center of frame)
    demo_zones = [
        ZoneDefinition(
            zone_id="demo-zone-1",
            name="Demo Zone",
            polygon=[
                [0.25, 0.25],
                [0.75, 0.25],
                [0.75, 0.75],
                [0.25, 0.75],
            ],
            color="#00FF00",
            is_active=True,
        )
    ]
    zone_analyzer.update_zones(demo_zones, frame_shape)

    # Re-create video source (since we released it)
    video_source = VideoSourceFactory.create(
        args.video, source_type="file", loop=args.loop
    )
    pipeline._video_source = video_source

    # Start pipeline
    logger.info("Starting pipeline...")
    pipeline.start()

    # Display loop
    logger.info("Press 'q' to quit")
    try:
        while callback.running:
            if callback.latest_frame is not None:
                cv2.imshow("Secure Sight Smoke Test", callback.latest_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

            time.sleep(0.01)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

    logger.info(
        "Smoke test complete. Processed %d frames.", pipeline.frame_count
    )


if __name__ == "__main__":
    main()
