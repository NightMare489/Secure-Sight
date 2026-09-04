"""
Application Configuration.

Centralized settings management using dataclasses.
All configuration is loaded from environment variables with sensible defaults.
"""

from __future__ import annotations

import os
from math import ceil
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DetectionConfig:
    """Configuration for the YOLO detection engine."""

    model_path: str = "yolov8s.pt"
    confidence_threshold: float = 0.5
    person_class_id: int = 0  # COCO class ID for 'person'
    device: str = "cuda"  # 'cuda', 'cpu', or device index
    img_size: int = 640


@dataclass(frozen=True)
class TrackerConfig:
    """Configuration for the ByteTrack tracker."""

    track_activation_threshold: float = 0.25
    lost_track_seconds: float = 4.0
    minimum_matching_threshold: float = 0.7
    frame_rate: float = 30.0

    @property
    def lost_track_buffer(self) -> int:
        """ByteTrack's 30 FPS-normalized buffer for the requested duration."""
        return max(1, ceil(self.lost_track_seconds * 30.0))


@dataclass(frozen=True)
class GlobalIdentityConfig:
    """Settings for associating local tracks across cameras."""

    enabled: bool = True
    association_window_seconds: float = 3.0


@dataclass(frozen=True)
class ReIDConfig:
    """Required OSNet appearance-embedding settings."""

    enabled: bool = True
    model_path: str = "models/osnet_x1_0_msmt17.pth"
    model_name: str = "osnet_x1_0"
    device: str = "cuda"
    similarity_threshold: float = 0.70
    min_crop_height: int = 64
    sample_interval_frames: int = 5


@dataclass(frozen=True)
class StreamConfig:
    """Configuration for video streaming."""

    frame_quality: int = 70  # JPEG quality (0-100)
    max_fps: int = 30
    frame_buffer_size: int = 5
    reconnect_delay: float = 3.0  # Seconds between reconnection attempts
    max_reconnect_attempts: int = 10


@dataclass(frozen=True)
class GeminiConfig:
    """Optional Gemini integration for the read-only analytics copilot."""

    api_key: str = ""
    model: str = "gemini-3.5-flash-lite"


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration for database connection."""

    uri: str = ""  # Will be computed from base_dir
    echo: bool = False  # SQLAlchemy query logging

    @staticmethod
    def default_uri(base_dir: Path) -> str:
        """Generate the default SQLite URI based on the project base directory."""
        db_path = base_dir / "data" / "securesight.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"


@dataclass(frozen=True)
class AppConfig:
    """Root application configuration."""

    # Flask
    debug: bool = True
    secret_key: str = "dev-secret-key-change-in-production"
    host: str = "0.0.0.0"
    port: int = 5000

    # CORS
    cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # Sub-configs
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    global_identity: GlobalIdentityConfig = field(
        default_factory=GlobalIdentityConfig
    )
    reid: ReIDConfig = field(default_factory=ReIDConfig)
    stream: StreamConfig = field(default_factory=StreamConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    # Paths
    base_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
    )
    snapshots_dir: Path = field(default=None)  # type: ignore[assignment]
    clips_dir: Path = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        """Compute derived paths after initialization."""
        if self.snapshots_dir is None:
            # frozen=True requires object.__setattr__
            object.__setattr__(
                self, "snapshots_dir", self.base_dir / "snapshots"
            )
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        if self.clips_dir is None:
            object.__setattr__(self, "clips_dir", self.base_dir / "incident_clips")
        self.clips_dir.mkdir(parents=True, exist_ok=True)

        # Set default database URI if not explicitly provided
        if not self.database.uri:
            default_uri = DatabaseConfig.default_uri(self.base_dir)
            object.__setattr__(
                self,
                "database",
                DatabaseConfig(uri=default_uri, echo=self.database.echo),
            )

    @classmethod
    def from_env(cls) -> AppConfig:
        """Create configuration from environment variables."""
        legacy_lost_buffer = os.getenv("TRACKER_LOST_BUFFER")
        lost_track_seconds = float(
            os.getenv(
                "TRACKER_LOST_SECONDS",
                str(float(legacy_lost_buffer) / 30.0)
                if legacy_lost_buffer is not None
                else "4.0",
            )
        )
        return cls(
            debug=os.getenv("FLASK_DEBUG", "true").lower() == "true",
            secret_key=os.getenv(
                "SECRET_KEY", "dev-secret-key-change-in-production"
            ),
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "5000")),
            detection=DetectionConfig(
                model_path=os.getenv("YOLO_MODEL", "yolov8s.pt"),
                confidence_threshold=float(
                    os.getenv("DETECTION_CONFIDENCE", "0.5")
                ),
                device=os.getenv("DETECTION_DEVICE", "cuda"),
            ),
            tracker=TrackerConfig(
                lost_track_seconds=lost_track_seconds,
                minimum_matching_threshold=float(
                    os.getenv("TRACKER_MATCHING_THRESHOLD", "0.7")
                ),
                frame_rate=float(os.getenv("TRACKER_FRAME_RATE", "30")),
            ),
            global_identity=GlobalIdentityConfig(
                enabled=os.getenv("GLOBAL_IDENTITY_ENABLED", "true").lower()
                == "true",
                association_window_seconds=float(
                    os.getenv("GLOBAL_IDENTITY_WINDOW_SECONDS", "3.0")
                ),
            ),
            reid=ReIDConfig(
                enabled=os.getenv("REID_ENABLED", "true").lower() == "true",
                model_path=os.getenv(
                    "REID_MODEL_PATH", "models/osnet_x1_0_msmt17.pth"
                ),
                model_name=os.getenv("REID_MODEL_NAME", "osnet_x1_0"),
                device=os.getenv("REID_DEVICE", os.getenv("DETECTION_DEVICE", "cuda")),
                similarity_threshold=float(
                    os.getenv("REID_SIMILARITY_THRESHOLD", "0.70")
                ),
                min_crop_height=int(os.getenv("REID_MIN_CROP_HEIGHT", "64")),
                sample_interval_frames=int(
                    os.getenv("REID_SAMPLE_INTERVAL_FRAMES", "5")
                ),
            ),
            stream=StreamConfig(
                frame_quality=int(os.getenv("STREAM_QUALITY", "70")),
                max_fps=int(os.getenv("STREAM_MAX_FPS", "30")),
            ),
            gemini=GeminiConfig(
                api_key=os.getenv("GEMINI_API_KEY", ""),
                model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            ),
        )
