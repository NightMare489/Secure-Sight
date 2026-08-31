"""
Alert SocketIO Events.

Handles client connections for real-time alert notifications.
"""

from __future__ import annotations

from flask_socketio import emit

from app.extensions import socketio
from app.utils.logger import get_logger

logger = get_logger(__name__)


@socketio.on("connect", namespace="/alerts")
def handle_alert_connect():
    """Handle client connection to the alerts namespace."""
    logger.info("Client connected to /alerts")
    emit("connected", {"message": "Connected to alerts"})


@socketio.on("disconnect", namespace="/alerts")
def handle_alert_disconnect():
    """Handle client disconnection from the alerts namespace."""
    logger.info("Client disconnected from /alerts")
