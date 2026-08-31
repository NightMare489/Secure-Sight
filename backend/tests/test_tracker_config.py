from __future__ import annotations

from app.config import AppConfig, TrackerConfig


def test_lost_track_seconds_converts_to_bytetrack_base_buffer() -> None:
    config = TrackerConfig(lost_track_seconds=4.0, frame_rate=25.0)

    # Supervision normalizes ByteTrack's buffer by frame_rate / 30.
    # 120 base frames therefore retain a 25 FPS track for four seconds.
    assert config.lost_track_buffer == 120
    assert int(config.frame_rate / 30.0 * config.lost_track_buffer) == 100


def test_legacy_lost_track_buffer_environment_remains_supported(monkeypatch) -> None:
    monkeypatch.setenv("TRACKER_LOST_BUFFER", "90")
    monkeypatch.delenv("TRACKER_LOST_SECONDS", raising=False)

    config = AppConfig.from_env().tracker

    assert config.lost_track_seconds == 3.0
    assert config.lost_track_buffer == 90
