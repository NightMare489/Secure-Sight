"""OSNet-only association of camera-local person tracks."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass

import numpy as np

from app.config import GlobalIdentityConfig
from app.core.interfaces import Detection


@dataclass(frozen=True)
class CameraIdentityConfig:
    """Stored camera metadata, retained independently of identity matching."""

    overlap_group: str | None = None
    ground_plane_homography: np.ndarray | None = None


@dataclass
class _TrackIdentity:
    global_person_id: str
    camera_id: str
    local_track_id: int
    last_seen: float
    embedding: np.ndarray | None = None
    cross_camera_associated: bool = False


class GlobalIdentityService:
    """Merge recent tracks from different cameras using OSNet cosine similarity."""

    def __init__(
        self,
        config: GlobalIdentityConfig | None = None,
        reid_similarity_threshold: float = 0.70,
        require_reid: bool = True,
    ) -> None:
        self._config = config or GlobalIdentityConfig()
        self._reid_similarity_threshold = reid_similarity_threshold
        self._require_reid = require_reid
        self._camera_configs: dict[str, CameraIdentityConfig] = {}
        self._identities: dict[tuple[str, int], _TrackIdentity] = {}
        self._lock = threading.RLock()

    def configure_camera(
        self,
        camera_id: str,
        overlap_group: str | None,
        ground_plane_homography: list[list[float]] | None,
    ) -> None:
        """Keep calibration metadata without applying it to identity matching."""
        matrix = None
        if ground_plane_homography is not None:
            candidate = np.asarray(ground_plane_homography, dtype=np.float64)
            if candidate.shape != (3, 3) or abs(np.linalg.det(candidate)) < 1e-12:
                raise ValueError("ground_plane_homography must be a non-singular 3x3 matrix")
            matrix = candidate
        with self._lock:
            self._camera_configs[camera_id] = CameraIdentityConfig(
                overlap_group=overlap_group or None,
                ground_plane_homography=matrix,
            )

    def clear_camera(self, camera_id: str) -> None:
        with self._lock:
            self._identities = {
                key: identity
                for key, identity in self._identities.items()
                if identity.camera_id != camera_id
            }

    def resolve(
        self,
        camera_id: str,
        detections: list[Detection],
        timestamp: float | None = None,
        embeddings: dict[int, np.ndarray] | None = None,
    ) -> list[Detection]:
        now = timestamp if timestamp is not None else time.time()
        with self._lock:
            self._purge_stale(now)
            for detection in detections:
                if detection.tracker_id is None:
                    continue
                identity = self._identities.setdefault(
                    (camera_id, detection.tracker_id),
                    _TrackIdentity(str(uuid.uuid4()), camera_id, detection.tracker_id, now),
                )
                identity.last_seen = now
                embedding = (embeddings or {}).get(detection.tracker_id)
                if embedding is not None:
                    identity.embedding = self._normalize(embedding)

                match = None
                if not identity.cross_camera_associated:
                    match = self._find_best_match(camera_id, identity, now)
                if match is not None:
                    self._merge_identities(identity, match)
                    detection.association_method = "reid"
                    detection.association_confidence = self._similarity(identity, match)
                elif identity.cross_camera_associated:
                    detection.association_method = "reid"
                    detection.association_confidence = 1.0
                else:
                    detection.association_method = "local_only"
                    detection.association_confidence = 1.0
                detection.global_person_id = identity.global_person_id
        return detections

    def _find_best_match(
        self, camera_id: str, identity: _TrackIdentity, timestamp: float
    ) -> _TrackIdentity | None:
        if not self._config.enabled or identity.embedding is None:
            return None
        best: _TrackIdentity | None = None
        best_similarity = self._reid_similarity_threshold
        for candidate in self._identities.values():
            if candidate is identity or candidate.camera_id == camera_id:
                continue
            if timestamp - candidate.last_seen > self._config.association_window_seconds:
                continue
            if candidate.embedding is None:
                continue
            similarity = self._similarity(identity, candidate)
            if similarity >= best_similarity:
                best, best_similarity = candidate, similarity
        return best

    @staticmethod
    def _normalize(embedding: np.ndarray) -> np.ndarray:
        vector = np.asarray(embedding, dtype=np.float32)
        return vector / max(float(np.linalg.norm(vector)), 1e-12)

    @staticmethod
    def _similarity(first: _TrackIdentity, second: _TrackIdentity) -> float:
        assert first.embedding is not None and second.embedding is not None
        return float(np.dot(first.embedding, second.embedding))

    def _merge_identities(self, identity: _TrackIdentity, candidate: _TrackIdentity) -> None:
        source_id, target_id = identity.global_person_id, candidate.global_person_id
        for known in self._identities.values():
            if known.global_person_id == source_id:
                known.global_person_id = target_id
        identity.cross_camera_associated = True
        candidate.cross_camera_associated = True

    def _purge_stale(self, timestamp: float) -> None:
        expiry = self._config.association_window_seconds * 2
        self._identities = {
            key: identity
            for key, identity in self._identities.items()
            if timestamp - identity.last_seen <= expiry
        }
