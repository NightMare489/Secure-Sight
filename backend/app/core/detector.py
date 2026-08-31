"""
Person Detector — YOLO Wrapper.

Implements IDetector using Ultralytics YOLOv8.
Filters detections to person class only (COCO class 0).

Follows Single Responsibility Principle: this class ONLY handles
running YOLO inference and converting results to our Detection DTOs.
"""

from __future__ import annotations

import numpy as np
from ultralytics import YOLO

from app.config import DetectionConfig
from app.core.interfaces import Detection, IDetector
from app.utils.exceptions import DetectorError, ModelLoadError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PersonDetector(IDetector):
    """
    YOLO-based person detector.

    Wraps the Ultralytics YOLO model to detect persons in video frames.
    Only returns detections for the 'person' class (class_id=0 in COCO).

    Args:
        config: Detection configuration with model path, confidence, etc.
    """

    def __init__(self, config: DetectionConfig) -> None:
        self._config = config
        self._model: YOLO | None = None
        self._load_model()

    def _load_model(self) -> None:
        """Load the YOLO model from the configured path."""
        try:
            logger.info(
                "Loading YOLO model from '%s' on device '%s'",
                self._config.model_path,
                self._config.device,
            )
            self._model = YOLO(self._config.model_path)
            logger.info("YOLO model loaded successfully")
        except Exception as e:
            raise ModelLoadError(self._config.model_path, str(e)) from e

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """
        Run person detection on a single frame.

        Args:
            frame: BGR image as numpy array (H, W, 3).

        Returns:
            List of Detection objects for persons found in the frame.

        Raises:
            DetectorError: If inference fails.
        """
        if self._model is None:
            raise DetectorError("Model not loaded")

        try:
            results = self._model(
                frame,
                conf=self._config.confidence_threshold,
                classes=[self._config.person_class_id],
                device=self._config.device,
                imgsz=self._config.img_size,
                verbose=False,
            )
        except Exception as e:
            raise DetectorError(f"Inference failed: {e}") from e

        return self._parse_results(results)

    def _parse_results(self, results: list) -> list[Detection]:
        """
        Parse YOLO results into our Detection DTOs.

        Args:
            results: Raw YOLO inference results.

        Returns:
            List of Detection objects.
        """
        detections: list[Detection] = []

        if not results or results[0].boxes is None:
            return detections

        boxes = results[0].boxes

        for i in range(len(boxes)):
            bbox = boxes.xyxy[i].cpu().numpy().astype(np.float32)
            confidence = float(boxes.conf[i].cpu().numpy())
            class_id = int(boxes.cls[i].cpu().numpy())

            detections.append(
                Detection(
                    bbox=bbox,
                    confidence=confidence,
                    class_id=class_id,
                    tracker_id=None,
                )
            )

        return detections

    def warmup(self) -> None:
        """
        Perform a warmup inference to initialize the model.

        Runs a single inference on a dummy image to trigger
        model compilation and CUDA memory allocation.
        """
        if self._model is None:
            raise DetectorError("Model not loaded — cannot warmup")

        logger.info("Warming up detector...")
        dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
        self.detect(dummy_frame)
        logger.info("Detector warmup complete")
