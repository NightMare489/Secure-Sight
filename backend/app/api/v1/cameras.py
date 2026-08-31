"""
Camera API Endpoints.

RESTful endpoints for camera CRUD operations.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.schemas.camera import CameraCreate, CameraUpdate
from app.services.camera_service import CameraService
from app.services.detection_service import DetectionServiceManager
from app.services.zone_service import ZoneService
from app.services.alert_service import AlertService

cameras_bp = Blueprint("cameras", __name__, url_prefix="/cameras")


def _get_camera_service() -> CameraService:
    """Create a CameraService with the current DB session."""
    return CameraService(db.session)


def _get_zone_service() -> ZoneService:
    """Create a ZoneService with the current DB session."""
    return ZoneService(db.session)


@cameras_bp.route("", methods=["GET"])
def list_cameras():
    """List all cameras."""
    service = _get_camera_service()
    cameras = service.get_all()

    # Enrich with pipeline status
    from flask import current_app
    detection_mgr: DetectionServiceManager = current_app.config.get(
        "DETECTION_MANAGER"
    )
    if detection_mgr:
        for cam in cameras:
            cam.pipeline_status = detection_mgr.get_pipeline_status(cam.id)

    return jsonify({
        "cameras": [c.model_dump() for c in cameras],
        "total": len(cameras),
    })


@cameras_bp.route("", methods=["POST"])
def create_camera():
    """Create a new camera."""
    data = CameraCreate.model_validate(request.get_json())
    service = _get_camera_service()
    camera = service.create(data)
    return jsonify(camera.model_dump()), 201


@cameras_bp.route("/<camera_id>", methods=["GET"])
def get_camera(camera_id: str):
    """Get a camera by ID."""
    service = _get_camera_service()
    camera = service.get_by_id(camera_id)

    from flask import current_app
    detection_mgr: DetectionServiceManager = current_app.config.get(
        "DETECTION_MANAGER"
    )
    if detection_mgr:
        camera.pipeline_status = detection_mgr.get_pipeline_status(camera.id)

    return jsonify(camera.model_dump())


@cameras_bp.route("/<camera_id>", methods=["PUT"])
def update_camera(camera_id: str):
    """Update a camera."""
    data = CameraUpdate.model_validate(request.get_json())
    service = _get_camera_service()
    camera = service.update(camera_id, data)
    return jsonify(camera.model_dump())


@cameras_bp.route("/<camera_id>", methods=["DELETE"])
def delete_camera(camera_id: str):
    """Delete a camera and all its zones."""
    # Stop pipeline if running
    from flask import current_app
    detection_mgr: DetectionServiceManager = current_app.config.get(
        "DETECTION_MANAGER"
    )
    if detection_mgr:
        try:
            detection_mgr.stop_pipeline(camera_id)
        except Exception:
            pass  # Pipeline wasn't running

    service = _get_camera_service()
    service.delete(camera_id)
    return jsonify({"message": "Camera deleted"}), 200


@cameras_bp.route("/<camera_id>/start", methods=["POST"])
def start_camera(camera_id: str):
    """Start the detection pipeline for a camera."""
    from flask import current_app

    camera_service = _get_camera_service()
    camera = camera_service.get_by_id(camera_id)

    zone_service = _get_zone_service()
    zones = zone_service.get_zone_definitions(camera_id)

    detection_mgr: DetectionServiceManager = current_app.config.get(
        "DETECTION_MANAGER"
    )
    if detection_mgr is None:
        return jsonify({"error": "Detection service not available"}), 503

    alert_service = AlertService(
        db.session,
        snapshots_dir=current_app.config.get("SNAPSHOTS_DIR"),
    )

    detection_mgr.start_pipeline(
        camera_id=camera.id,
        source_uri=camera.source_uri,
        source_type=camera.source_type,
        zones=zones,
        alert_service=alert_service,
        overlap_group=camera.overlap_group,
        ground_plane_homography=camera.ground_plane_homography,
    )

    return jsonify({"message": "Pipeline started", "camera_id": camera.id})


@cameras_bp.route("/<camera_id>/stop", methods=["POST"])
def stop_camera(camera_id: str):
    """Stop the detection pipeline for a camera."""
    from flask import current_app

    detection_mgr: DetectionServiceManager = current_app.config.get(
        "DETECTION_MANAGER"
    )
    if detection_mgr is None:
        return jsonify({"error": "Detection service not available"}), 503

    detection_mgr.stop_pipeline(camera_id)
    return jsonify({"message": "Pipeline stopped", "camera_id": camera_id})


@cameras_bp.route("/<camera_id>/thumbnail", methods=["GET"])
def get_camera_thumbnail(camera_id: str):
    """Grab the first frame from the camera source as a thumbnail."""
    from flask import send_file
    import io
    import cv2
    from app.core.video_source import VideoSourceFactory

    camera_service = _get_camera_service()
    camera = camera_service.get_by_id(camera_id)

    try:
        # Create video source
        video_source = VideoSourceFactory.create(
            camera.source_uri, source_type=camera.source_type, loop=False
        )
        video_source.open()
        success, frame = video_source.read()
        video_source.release()

        if success and frame is not None:
            # Encode frame as JPEG
            success_encode, encoded_image = cv2.imencode(".jpg", frame)
            if success_encode:
                return send_file(
                    io.BytesIO(encoded_image.tobytes()),
                    mimetype="image/jpeg"
                )
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Failed to generate thumbnail for camera {camera_id}: {e}")

    return jsonify({"error": "Failed to generate thumbnail"}), 404
