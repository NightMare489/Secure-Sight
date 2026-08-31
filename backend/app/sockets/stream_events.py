"""
Camera Stream SocketIO Events.

Handles client connections for live camera video streaming.
Uses SocketIO rooms to manage per-camera subscriptions.
"""

from __future__ import annotations

from flask_socketio import emit, join_room, leave_room

from app.extensions import socketio
from app.utils.logger import get_logger

logger = get_logger(__name__)


@socketio.on("connect", namespace="/stream")
def handle_stream_connect():
    """Handle client connection to the stream namespace."""
    logger.info("Client connected to /stream")
    emit("connected", {"message": "Connected to stream"})


@socketio.on("disconnect", namespace="/stream")
def handle_stream_disconnect():
    """Handle client disconnection from the stream namespace."""
    logger.info("Client disconnected from /stream")


@socketio.on("join_camera", namespace="/stream")
def handle_join_camera(data: dict):
    """
    Subscribe to a camera's live feed.

    Client sends: {"camera_id": "uuid-string"}
    """
    camera_id = data.get("camera_id")
    if not camera_id:
        emit("error", {"message": "camera_id is required"})
        return

    room = f"camera_{camera_id}"
    join_room(room)
    logger.info("Client joined room: %s", room)
    emit("joined", {"camera_id": camera_id, "room": room})


@socketio.on("leave_camera", namespace="/stream")
def handle_leave_camera(data: dict):
    """
    Unsubscribe from a camera's live feed.

    Client sends: {"camera_id": "uuid-string"}
    """
    camera_id = data.get("camera_id")
    if not camera_id:
        emit("error", {"message": "camera_id is required"})
        return

    room = f"camera_{camera_id}"
    leave_room(room)
    logger.info("Client left room: %s", room)
    emit("left", {"camera_id": camera_id})
