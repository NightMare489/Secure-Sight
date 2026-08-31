"""
Alert API Endpoints.

RESTful endpoints for querying alerts.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.schemas.alert import AlertFilter
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
