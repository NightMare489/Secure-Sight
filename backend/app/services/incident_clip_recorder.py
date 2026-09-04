"""Short incident-video capture built from the live pipeline frames."""

from __future__ import annotations

import threading
import time
import subprocess
from collections import deque
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from app.utils.logger import get_logger

logger = get_logger(__name__)


class IncidentClipRecorder:
    """Keeps a five-second rolling buffer and finishes clips after five seconds."""

    def __init__(
        self,
        camera_id: str,
        clips_dir: Path,
        fps: int,
        on_completed: Callable[[str, str], None],
        seconds_before: float = 5.0,
        seconds_after: float = 5.0,
    ) -> None:
        self._camera_id = camera_id
        self._clips_dir = clips_dir
        self._fps = max(1, fps)
        self._on_completed = on_completed
        self._before = seconds_before
        self._after = seconds_after
        self._frames: deque[tuple[float, np.ndarray]] = deque()
        self._pending: dict[str, dict] = {}
        self._lock = threading.Lock()

    def capture(self, frame: np.ndarray | None, timestamp: float | None = None) -> None:
        """Add a frame and complete any clips whose after-window elapsed."""
        if frame is None:
            return
        now = timestamp or time.time()
        completed: list[tuple[str, list[tuple[float, np.ndarray]]]] = []
        with self._lock:
            self._frames.append((now, frame.copy()))
            while self._frames and self._frames[0][0] < now - self._before:
                self._frames.popleft()
            for alert_id, pending in list(self._pending.items()):
                pending["frames"].append((now, frame.copy()))
                if now >= pending["until"]:
                    completed.append((alert_id, pending["frames"]))
                    del self._pending[alert_id]
        for alert_id, frames in completed:
            threading.Thread(target=self._write_clip, args=(alert_id, frames), daemon=True).start()

    def start_incident(self, alert_id: str, timestamp: float | None = None) -> None:
        """Freeze the current pre-incident window and collect the following five seconds."""
        now = timestamp or time.time()
        with self._lock:
            if alert_id in self._pending:
                return
            frames = [(ts, frame.copy()) for ts, frame in self._frames if ts >= now - self._before]
            self._pending[alert_id] = {"until": now + self._after, "frames": frames}

    def _write_clip(self, alert_id: str, frames: list[tuple[float, np.ndarray]]) -> None:
        if not frames:
            return
        try:
            self._clips_dir.mkdir(parents=True, exist_ok=True)
            height, width = frames[0][1].shape[:2]
            basename = f"{self._camera_id}_{alert_id}_{int(time.time() * 1000)}"
            temporary_path = self._clips_dir / f"{basename}.avi"
            path = self._clips_dir / f"{basename}.mp4"
            elapsed = max(0.1, frames[-1][0] - frames[0][0])
            fps = min(30, max(1, round((len(frames) - 1) / elapsed)))
            writer = cv2.VideoWriter(str(temporary_path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (width, height))
            if not writer.isOpened():
                raise RuntimeError("OpenCV could not create MP4 writer")
            for _, frame in frames:
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height))
                writer.write(frame)
            writer.release()
            # Chrome reliably plays H.264 MP4. OpenCV's default `mp4v` output
            # is MPEG-4 Part 2, which many browsers refuse to decode.
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(temporary_path), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path)],
                check=True,
                capture_output=True,
            )
            temporary_path.unlink(missing_ok=True)
            self._on_completed(alert_id, str(path))
            logger.info("Saved incident clip for alert %s", alert_id)
        except Exception as exc:
            logger.error("Failed to save incident clip for %s: %s", alert_id, exc)
