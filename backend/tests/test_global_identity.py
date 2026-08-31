from __future__ import annotations

import numpy as np

from app.config import GlobalIdentityConfig
from app.core.global_identity import GlobalIdentityService
from app.core.interfaces import Detection


def _detection(tracker_id: int = 1) -> Detection:
    return Detection(
        bbox=np.asarray([10, 20, 40, 100], dtype=np.float32),
        confidence=0.95,
        class_id=0,
        tracker_id=tracker_id,
    )


def test_merges_similar_embeddings_immediately_without_calibration() -> None:
    service = GlobalIdentityService(
        GlobalIdentityConfig(enabled=True), reid_similarity_threshold=0.7
    )
    embedding = np.asarray([0.6, 0.8], dtype=np.float32)

    first = service.resolve("camera-a", [_detection()], 100.0, {1: embedding})[0]
    second = service.resolve("camera-b", [_detection()], 100.1, {1: embedding})[0]

    assert first.global_person_id == second.global_person_id
    assert second.association_method == "reid"
    assert second.association_confidence == 1.0


def test_rejects_incompatible_embeddings() -> None:
    service = GlobalIdentityService(
        GlobalIdentityConfig(enabled=True), reid_similarity_threshold=0.7
    )

    first = service.resolve(
        "camera-a", [_detection()], 100.0, {1: np.asarray([1.0, 0.0])}
    )[0]
    second = service.resolve(
        "camera-b", [_detection()], 100.1, {1: np.asarray([0.0, 1.0])}
    )[0]

    assert first.global_person_id != second.global_person_id
    assert second.association_method == "local_only"


def test_same_camera_track_keeps_its_global_id() -> None:
    service = GlobalIdentityService()
    embedding = np.asarray([0.6, 0.8], dtype=np.float32)

    first = service.resolve("camera-a", [_detection()], 100.0, {1: embedding})[0]
    second = service.resolve("camera-a", [_detection()], 100.1, {1: embedding})[0]

    assert first.global_person_id == second.global_person_id
    assert second.association_method == "local_only"


def test_does_not_merge_tracks_without_osnet_embeddings() -> None:
    service = GlobalIdentityService()

    first = service.resolve("camera-a", [_detection()], 100.0)[0]
    second = service.resolve("camera-b", [_detection()], 100.1)[0]

    assert first.global_person_id != second.global_person_id
