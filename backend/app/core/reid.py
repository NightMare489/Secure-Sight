"""Person appearance embeddings for cross-camera re-identification."""

from __future__ import annotations

from pathlib import Path
import threading

import numpy as np

from app.config import ReIDConfig
from app.core.interfaces import Detection
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PersonReIdentifier:
    """Extract L2-normalized OSNet embeddings from tracked person crops.

    Torchreid is imported lazily at backend startup. ``model_path`` must point
    to OSNet ReID weights, not YOLO weights.
    """

    def __init__(self, config: ReIDConfig) -> None:
        if not config.enabled:
            raise ValueError("PersonReIdentifier requires REID_ENABLED=true")
        if not config.model_path:
            raise ValueError("REID_MODEL_PATH is required when REID_ENABLED=true")
        model_path = Path(config.model_path)
        if not model_path.is_absolute():
            model_path = Path(__file__).resolve().parents[2] / model_path
        if not model_path.is_file():
            raise FileNotFoundError(f"ReID weights not found: {model_path}")

        try:
            from torchreid.reid.utils import FeatureExtractor
        except ImportError as error:
            raise RuntimeError(
                "Torchreid is required. Run 'pip install -r requirements.txt'."
            ) from error

        self._config = config
        self._extractor = FeatureExtractor(
            model_name=config.model_name,
            model_path=str(model_path),
            device=config.device,
        )
        self._lock = threading.Lock()
        logger.info("Loaded ReID model '%s'", config.model_name)

    def encode(
        self,
        frame: np.ndarray,
        detections: list[Detection],
        frame_number: int,
    ) -> dict[int, np.ndarray]:
        """Return embeddings for eligible tracked detections on sampled frames."""
        if frame_number % self._config.sample_interval_frames != 0:
            return {}

        crops: list[np.ndarray] = []
        tracker_ids: list[int] = []
        height, width = frame.shape[:2]
        for detection in detections:
            if detection.tracker_id is None:
                continue
            x1, y1, x2, y2 = detection.bbox.astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(width, x2), min(height, y2)
            if x2 <= x1 or y2 - y1 < self._config.min_crop_height:
                continue
            crops.append(frame[y1:y2, x1:x2].copy())
            tracker_ids.append(detection.tracker_id)

        if not crops:
            return {}

        with self._lock:
            features = self._extractor(crops)
        vectors = features.detach().cpu().numpy().astype(np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors /= np.maximum(norms, 1e-12)
        return dict(zip(tracker_ids, vectors))
