"""
Alert API Endpoints.

RESTful endpoints for querying alerts.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, send_file
from pathlib import Path

from app.extensions import db
from app.schemas.alert import AlertAcknowledge, AlertFilter
from app.services.alert_service import AlertService

alerts_bp = Blueprint("alerts", __name__, url_prefix="/alerts")


def _get_alert_service() -> AlertService:
    """Create an AlertService with the current DB session."""
    from flask import current_app

    return AlertService(
        db.session,
        snapshots_dir=current_app.config.get("SNAPSHOTS_DIR"),
    )


@alerts_bp.route("", methods=["GET"])
def list_alerts():
    """
    List alerts with filtering and pagination.

    Query params: camera_id, zone_id, event_type, start_time, end_time, page, per_page
    """
    filters = AlertFilter(
        camera_id=request.args.get("camera_id"),
        zone_id=request.args.get("zone_id"),
        event_type=request.args.get("event_type"),
        start_time=request.args.get("start_time"),
        end_time=request.args.get("end_time"),
        page=int(request.args.get("page", 1)),
        per_page=int(request.args.get("per_page", 50)),
        acknowledged=(request.args.get("acknowledged", "").lower() == "true") if request.args.get("acknowledged") is not None else None,
    )

    service = _get_alert_service()
    result = service.get_alerts(filters)
    return jsonify(result.model_dump())


@alerts_bp.route("/<alert_id>", methods=["GET"])
def get_alert(alert_id: str):
    """Get a specific alert by ID."""
    service = _get_alert_service()
    alert = service.get_by_id(alert_id)
    return jsonify(alert.model_dump())


@alerts_bp.route("/<alert_id>/acknowledge", methods=["PUT"])
def acknowledge_alert(alert_id: str):
    """Acknowledge an alert with an optional operator note."""
    data = AlertAcknowledge.model_validate(request.get_json() or {})
    alert = _get_alert_service().acknowledge(alert_id, data.acknowledged, data.note)
    return jsonify(alert.model_dump())


@alerts_bp.route("/<alert_id>/snapshot", methods=["GET"])
def get_alert_snapshot(alert_id: str):
    """Serve an alert snapshot only when it belongs to the configured directory."""
    alert = _get_alert_service().get_by_id(alert_id)
    if not alert.snapshot_path:
        return jsonify({"error": "This alert has no snapshot"}), 404
    snapshots_dir = Path(current_app.config["SNAPSHOTS_DIR"]).resolve()
    snapshot_path = Path(alert.snapshot_path).resolve()
    if snapshots_dir not in snapshot_path.parents or not snapshot_path.is_file():
        return jsonify({"error": "Snapshot not found"}), 404
    return send_file(snapshot_path, mimetype="image/jpeg")


@alerts_bp.route("/<alert_id>/clip", methods=["GET"])
def get_alert_clip(alert_id: str):
    """Serve a completed incident clip (five seconds before and after)."""
    alert = _get_alert_service().get_by_id(alert_id)
    if not alert.clip_path:
        return jsonify({"error": "This alert clip is still being prepared or unavailable"}), 404
    clips_dir = Path(current_app.config["CLIPS_DIR"]).resolve()
    clip_path = Path(alert.clip_path).resolve()
    if clips_dir not in clip_path.parents or not clip_path.is_file():
        return jsonify({"error": "Clip not found"}), 404
    return send_file(clip_path, mimetype="video/mp4")


@alerts_bp.route("/recent", methods=["GET"])
def get_recent_alerts():
    """Get the most recent alerts."""
    limit = int(request.args.get("limit", 20))
    service = _get_alert_service()
    alerts = service.get_recent(limit)
    return jsonify({
        "alerts": [a.model_dump() for a in alerts],
        "total": len(alerts),
    })
