"""
Custom Exception Definitions.

Structured exception hierarchy for clean error handling across the application.
All custom exceptions inherit from a common base for easy catching.
"""

from __future__ import annotations


class SchoolCVError(Exception):
    """Base exception for all SchoolCV application errors."""

    def __init__(self, message: str = "", code: str = "UNKNOWN_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Core Engine Exceptions
# ---------------------------------------------------------------------------

class DetectorError(SchoolCVError):
    """Raised when the detection engine encounters an error."""

    def __init__(self, message: str = "Detection engine error") -> None:
        super().__init__(message, code="DETECTOR_ERROR")


class ModelLoadError(DetectorError):
    """Raised when a YOLO model fails to load."""

    def __init__(self, model_path: str, reason: str = "") -> None:
        detail = f"Failed to load model '{model_path}'"
        if reason:
            detail += f": {reason}"
        super().__init__(detail)
        self.model_path = model_path


class TrackerError(SchoolCVError):
    """Raised when the tracking engine encounters an error."""

    def __init__(self, message: str = "Tracker error") -> None:
        super().__init__(message, code="TRACKER_ERROR")


# ---------------------------------------------------------------------------
# Video Source Exceptions
# ---------------------------------------------------------------------------

class VideoSourceError(SchoolCVError):
    """Raised when a video source cannot be opened or read."""

    def __init__(self, source: str, reason: str = "") -> None:
        detail = f"Video source error for '{source}'"
        if reason:
            detail += f": {reason}"
        super().__init__(detail, code="VIDEO_SOURCE_ERROR")
        self.source = source


class VideoSourceConnectionError(VideoSourceError):
    """Raised when a video source fails to connect."""

    def __init__(self, source: str) -> None:
        super().__init__(source, reason="Failed to connect/open source")


class VideoSourceReadError(VideoSourceError):
    """Raised when a frame cannot be read from the video source."""

    def __init__(self, source: str) -> None:
        super().__init__(source, reason="Failed to read frame")


# ---------------------------------------------------------------------------
# Pipeline Exceptions
# ---------------------------------------------------------------------------

class PipelineError(SchoolCVError):
    """Raised when the detection pipeline encounters an error."""

    def __init__(self, message: str = "Pipeline error") -> None:
        super().__init__(message, code="PIPELINE_ERROR")


class PipelineAlreadyRunningError(PipelineError):
    """Raised when attempting to start an already-running pipeline."""

    def __init__(self, camera_id: str) -> None:
        super().__init__(f"Pipeline for camera '{camera_id}' is already running")
        self.camera_id = camera_id


class PipelineNotRunningError(PipelineError):
    """Raised when attempting to stop a pipeline that isn't running."""

    def __init__(self, camera_id: str) -> None:
        super().__init__(f"Pipeline for camera '{camera_id}' is not running")
        self.camera_id = camera_id


# ---------------------------------------------------------------------------
# Data Layer Exceptions
# ---------------------------------------------------------------------------

class NotFoundError(SchoolCVError):
    """Raised when a requested resource is not found."""

    def __init__(self, resource_type: str, resource_id: str) -> None:
        super().__init__(
            f"{resource_type} with id '{resource_id}' not found",
            code="NOT_FOUND",
        )
        self.resource_type = resource_type
        self.resource_id = resource_id


class ValidationError(SchoolCVError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str = "") -> None:
        self.field = field
        detail = f"Validation error"
        if field:
            detail += f" on field '{field}'"
        detail += f": {message}"
        super().__init__(detail, code="VALIDATION_ERROR")


class DuplicateError(SchoolCVError):
    """Raised when a duplicate resource is detected."""

    def __init__(self, resource_type: str, identifier: str) -> None:
        super().__init__(
            f"{resource_type} '{identifier}' already exists",
            code="DUPLICATE_ERROR",
        )
