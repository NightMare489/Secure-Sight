"""
Flask Extensions.

Centralized initialization of Flask extensions.
Extensions are created here and initialized with the app in the factory.
"""

from __future__ import annotations

from flask_cors import CORS
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy

# Database
db = SQLAlchemy()

# Real-time communication
socketio = SocketIO()

# CORS
cors = CORS()
