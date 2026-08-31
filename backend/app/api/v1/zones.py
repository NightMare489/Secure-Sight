"""
Zone API Endpoints.

RESTful endpoints for zone CRUD operations.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.schemas.zone import ZoneCreate, ZoneUpdate
from app.services.zone_service import ZoneService
from app.services.detection_service import DetectionServiceManager

zones_bp = Blueprint("zones", __name__)


def _get_zone_service() -> ZoneService:
    """Create a ZoneService with the current DB session."""
    return ZoneService(db.session)


@zones_bp.route("/cameras/<camera_id>/zones", methods=["GET"])
def list_zones(camera_id: str):
    """List all zones for a camera."""
    service = _get_zone_service()
    zones = service.get_by_camera_id(camera_id)
    return jsonify({
        "zones": [z.model_dump() for z in zones],
        "total": len(zones),
    })


@zones_bp.route("/cameras/<camera_id>/zones", methods=["POST"])
def create_zone(camera_id: str):
    """Create a new zone for a camera."""
    data = ZoneCreate.model_validate(request.get_json())
    service = _get_zone_service()
    zone = service.create(camera_id, data)

    # Hot-reload zones in running pipeline
    _hot_reload_zones(camera_id)

    return jsonify(zone.model_dump()), 201


@zones_bp.route("/zones/<zone_id>", methods=["GET"])
def get_zone(zone_id: str):
    """Get a zone by ID."""
    service = _get_zone_service()
    zone = service.get_by_id(zone_id)
    return jsonify(zone.model_dump())


@zones_bp.route("/zones/<zone_id>", methods=["PUT"])
def update_zone(zone_id: str):
    """Update a zone."""
    data = ZoneUpdate.model_validate(request.get_json())
    service = _get_zone_service()
    zone = service.update(zone_id, data)

    # Hot-reload zones in running pipeline
    _hot_reload_zones(zone.camera_id)

    return jsonify(zone.model_dump())


@zones_bp.route("/zones/<zone_id>", methods=["DELETE"])
def delete_zone(zone_id: str):
    """Delete a zone."""
    service = _get_zone_service()

    # Get camera_id before deletion for hot-reload
    zone = service.get_by_id(zone_id)
    camera_id = zone.camera_id

    service.delete(zone_id)

    # Hot-reload zones in running pipeline
    _hot_reload_zones(camera_id)

    return jsonify({"message": "Zone deleted"}), 200


def _hot_reload_zones(camera_id: str) -> None:
    """
    Hot-reload zones in a running detection pipeline.

    If the camera has an active pipeline, update its zones
    without requiring a restart.
    """
    from flask import current_app

    detection_mgr: DetectionServiceManager = current_app.config.get(
        "DETECTION_MANAGER"
    )
    if detection_mgr is None:
        return

    service = _get_zone_service()
    zone_defs = service.get_zone_definitions(camera_id)
    detection_mgr.update_zones(camera_id, zone_defs)
