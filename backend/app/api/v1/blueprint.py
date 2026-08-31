"""
V1 API Blueprint Aggregator.

Registers all v1 sub-blueprints under /api/v1 prefix.
"""

from __future__ import annotations

from flask import Blueprint

from app.api.v1.cameras import cameras_bp
from app.api.v1.zones import zones_bp
from app.api.v1.alerts import alerts_bp

v1_bp = Blueprint("v1", __name__, url_prefix="/api/v1")

# Register sub-blueprints
v1_bp.register_blueprint(cameras_bp)
v1_bp.register_blueprint(zones_bp)
v1_bp.register_blueprint(alerts_bp)
