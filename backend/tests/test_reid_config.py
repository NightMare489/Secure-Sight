from __future__ import annotations

from app.config import ReIDConfig


def test_reid_uses_the_bundled_osnet_x1_0_weights_by_default() -> None:
    config = ReIDConfig()

    assert config.enabled is True
    assert config.model_name == "osnet_x1_0"
    assert config.model_path == "models/osnet_x1_0_msmt17.pth"
    assert config.similarity_threshold == 0.70
    assert config.sample_interval_frames == 5
