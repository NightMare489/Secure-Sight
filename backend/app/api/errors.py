"""
API Error Handlers.

Centralized error handling that maps custom exceptions to HTTP responses.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from app.utils.exceptions import (
    DuplicateError,
    NotFoundError,
    PipelineAlreadyRunningError,
    PipelineNotRunningError,
    SecureSightError,
    ValidationError,
)

errors_bp = Blueprint("errors", __name__)


@errors_bp.app_errorhandler(NotFoundError)
def handle_not_found(error: NotFoundError):
    """Handle 404 Not Found errors."""
    return jsonify({"error": error.message, "code": error.code}), 404


@errors_bp.app_errorhandler(ValidationError)
def handle_validation_error(error: ValidationError):
    """Handle 400 Validation errors."""
    return (
        jsonify(
            {"error": error.message, "code": error.code, "field": error.field}
        ),
        400,
    )


@errors_bp.app_errorhandler(DuplicateError)
def handle_duplicate(error: DuplicateError):
    """Handle 409 Conflict errors."""
    return jsonify({"error": error.message, "code": error.code}), 409


@errors_bp.app_errorhandler(PipelineAlreadyRunningError)
def handle_pipeline_running(error: PipelineAlreadyRunningError):
    """Handle 409 Pipeline already running."""
    return jsonify({"error": error.message, "code": error.code}), 409


@errors_bp.app_errorhandler(PipelineNotRunningError)
def handle_pipeline_not_running(error: PipelineNotRunningError):
    """Handle 404 Pipeline not running."""
    return jsonify({"error": error.message, "code": error.code}), 404


@errors_bp.app_errorhandler(SecureSightError)
def handle_app_error(error: SecureSightError):
    """Handle generic application errors."""
    return jsonify({"error": error.message, "code": error.code}), 500


@errors_bp.app_errorhandler(400)
def handle_bad_request(error):
    """Handle 400 Bad Request."""
    return jsonify({"error": "Bad request", "code": "BAD_REQUEST"}), 400


@errors_bp.app_errorhandler(404)
def handle_http_not_found(error):
    """Handle 404 Not Found."""
    return jsonify({"error": "Resource not found", "code": "NOT_FOUND"}), 404


@errors_bp.app_errorhandler(500)
def handle_internal_error(error):
    """Handle 500 Internal Server Error."""
    return (
        jsonify({"error": "Internal server error", "code": "INTERNAL_ERROR"}),
        500,
    )
