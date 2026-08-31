"""
Video Source Abstractions.

Implements IVideoSource for different input types:
- FileVideoSource: Video files (.mp4, .avi, etc.)
- RTSPVideoSource: RTSP camera streams
- WebcamVideoSource: USB/built-in webcams

Also provides a VideoSourceFactory for creating the right source
from a URI string (Factory Pattern).
"""

from __future__ import annotations

import cv2
import numpy as np

from app.core.interfaces import IVideoSource
from app.utils.exceptions import VideoSourceConnectionError, VideoSourceReadError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class _BaseVideoSource(IVideoSource):
    """
    Base implementation for OpenCV-based video sources.

    Provides shared logic for opening, reading, and releasing
    video captures. Subclasses customize connection behavior.
    """

    def __init__(self, source: str | int) -> None:
        self._source = source
        self._capture: cv2.VideoCapture | None = None
        self._frame_width: int = 0
        self._frame_height: int = 0
        self._fps: float = 0.0

    def open(self) -> None:
        """Open the video source."""
        logger.info("Opening video source: %s", self._source)
        self._capture = cv2.VideoCapture(self._source)

        if not self._capture.isOpened():
            raise VideoSourceConnectionError(str(self._source))

        self._frame_width = int(
            self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        )
        self._frame_height = int(
            self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        )
        self._fps = self._capture.get(cv2.CAP_PROP_FPS) or 30.0

        logger.info(
            "Video source opened: %dx%d @ %.1f FPS",
            self._frame_width,
            self._frame_height,
            self._fps,
        )

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read the next frame."""
        if self._capture is None or not self._capture.isOpened():
            return False, None

        ret, frame = self._capture.read()
        return ret, frame if ret else None

    def release(self) -> None:
        """Release the video capture."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
            logger.info("Video source released: %s", self._source)

    def is_opened(self) -> bool:
        """Check if the video source is open."""
        return self._capture is not None and self._capture.isOpened()

    @property
    def frame_width(self) -> int:
        return self._frame_width

    @property
    def frame_height(self) -> int:
        return self._frame_height

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def source_uri(self) -> str:
        return str(self._source)


class FileVideoSource(_BaseVideoSource):
    """
    Video file source.

    Supports .mp4, .avi, .mkv, and other OpenCV-compatible formats.
    When the file ends, read() returns (False, None).

    Args:
        file_path: Path to the video file.
        loop: If True, restart from the beginning when the video ends.
    """

    def __init__(self, file_path: str, loop: bool = False) -> None:
        from pathlib import Path
        path = Path(file_path)
        
        # If path is relative, resolve it against backend root or repo root
        if not path.is_absolute():
            backend_root = Path(__file__).resolve().parents[2]
            resolved_path = backend_root / path
            
            # If not found in backend root, check one level up (repo root)
            if not resolved_path.exists():
                repo_root = backend_root.parent
                if (repo_root / path).exists():
                    resolved_path = repo_root / path
                    
            file_path = str(resolved_path)
            
        super().__init__(file_path)
        self._loop = loop

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read the next frame, optionally looping."""
        ret, frame = super().read()

        if not ret and self._loop and self._capture is not None:
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = super().read()

        return ret, frame


class RTSPVideoSource(_BaseVideoSource):
    """
    RTSP camera stream source.

    Connects to an RTSP URL and reads frames. Includes
    connection timeout handling.

    Args:
        rtsp_url: RTSP stream URL (e.g., rtsp://user:pass@192.168.1.100/stream).
    """

    def __init__(self, rtsp_url: str) -> None:
        super().__init__(rtsp_url)

    def open(self) -> None:
        """Open the RTSP stream with optimized settings."""
        logger.info("Connecting to RTSP stream: %s", self._source)

        # Use FFMPEG backend for better RTSP handling
        self._capture = cv2.VideoCapture(
            self._source, cv2.CAP_FFMPEG
        )

        if self._capture is not None:
            # Reduce buffer size for lower latency
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not self._capture or not self._capture.isOpened():
            raise VideoSourceConnectionError(str(self._source))

        self._frame_width = int(
            self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)
        )
        self._frame_height = int(
            self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
        )
        self._fps = self._capture.get(cv2.CAP_PROP_FPS) or 30.0

        logger.info(
            "RTSP stream connected: %dx%d @ %.1f FPS",
            self._frame_width,
            self._frame_height,
            self._fps,
        )


class WebcamVideoSource(_BaseVideoSource):
    """
    USB/built-in webcam source.

    Args:
        device_index: Camera device index (default: 0 for primary camera).
    """

    def __init__(self, device_index: int = 0) -> None:
        super().__init__(device_index)


class VideoSourceFactory:
    """
    Factory for creating video source instances from URI strings.

    Determines the appropriate source type based on the URI format:
    - File paths → FileVideoSource
    - rtsp:// URLs → RTSPVideoSource
    - Numeric strings → WebcamVideoSource

    This follows the Open/Closed Principle — add new source types
    by extending this factory without modifying existing sources.
    """

    @staticmethod
    def create(
        source_uri: str,
        source_type: str = "auto",
        loop: bool = False,
    ) -> IVideoSource:
        """
        Create the appropriate video source from a URI string.

        Args:
            source_uri: Video source URI (file path, RTSP URL, or device index).
            source_type: Explicit type ("file", "rtsp", "webcam", "auto").
            loop: Whether to loop video files (only for FileVideoSource).

        Returns:
            IVideoSource implementation.
        """
        if source_type == "auto":
            source_type = VideoSourceFactory._detect_type(source_uri)

        if source_type == "file":
            return FileVideoSource(source_uri, loop=loop)
        elif source_type == "rtsp":
            return RTSPVideoSource(source_uri)
        elif source_type == "webcam":
            device_index = int(source_uri) if source_uri.isdigit() else 0
            return WebcamVideoSource(device_index)
        else:
            raise ValueError(f"Unknown source type: '{source_type}'")

    @staticmethod
    def _detect_type(source_uri: str) -> str:
        """Auto-detect the source type from the URI string."""
        uri_lower = source_uri.lower()

        if uri_lower.startswith("rtsp://") or uri_lower.startswith("rtsps://"):
            return "rtsp"
        elif uri_lower.startswith("http://") or uri_lower.startswith("https://"):
            return "rtsp"  # IP cameras often use HTTP
        elif source_uri.isdigit():
            return "webcam"
        else:
            return "file"
