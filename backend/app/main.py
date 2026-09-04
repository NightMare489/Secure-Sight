"""
Flask Application Factory.

Creates and configures the Flask application following the factory pattern.
All extensions, blueprints, and services are initialized here.
"""

from __future__ import annotations

import atexit
from pathlib import Path

from flask import Flask

from app.config import AppConfig
from app.extensions import cors, db, socketio
from app.utils.logger import get_logger

logger = get_logger(__name__)


def create_app(config: AppConfig | None = None) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        config: Application configuration. If None, loads from environment.

    Returns:
        Configured Flask application.
    """
    if config is None:
        config = AppConfig.from_env()

    app = Flask(__name__)

    # Flask configuration
    app.config["SECRET_KEY"] = config.secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = config.database.uri
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ECHO"] = config.database.echo
    app.config["SNAPSHOTS_DIR"] = config.snapshots_dir
    app.config["CLIPS_DIR"] = config.clips_dir
    app.config["GEMINI_CONFIG"] = config.gemini

    # Initialize extensions
    _init_extensions(app, config)

    # Register blueprints
    _register_blueprints(app)

    # Register SocketIO events
    _register_socket_events()

    # Initialize services
    _init_services(app, config)

    # Create database tables
    with app.app_context():
        from app.models import Base
        from app.db_migrations import apply_additive_migrations

        Base.metadata.create_all(bind=db.engine)
        apply_additive_migrations(db.engine)
        logger.info("Database tables created/verified")

    logger.info("Application initialized successfully")
    return app


def _init_extensions(app: Flask, config: AppConfig) -> None:
    """Initialize Flask extensions."""
    db.init_app(app)

    socketio.init_app(
        app,
        cors_allowed_origins=config.cors_origins,
        async_mode="threading",
        logger=False,
        engineio_logger=False,
    )

    cors.init_app(app, origins=config.cors_origins)

    logger.info("Extensions initialized")


def _register_blueprints(app: Flask) -> None:
    """Register all API blueprints."""
    from app.api.errors import errors_bp
    from app.api.v1.blueprint import v1_bp

    app.register_blueprint(errors_bp)
    app.register_blueprint(v1_bp)

    logger.info("Blueprints registered")


def _register_socket_events() -> None:
    """Import SocketIO event handlers to register them."""
    import app.sockets.stream_events  # noqa: F401
    import app.sockets.alert_events  # noqa: F401

    logger.info("SocketIO event handlers registered")


def _init_services(app: Flask, config: AppConfig) -> None:
    """Initialize application services."""
    from app.services.detection_service import DetectionServiceManager

    detection_manager = DetectionServiceManager(
        config=config,
        socketio=socketio,
        app=app,
    )

    app.config["DETECTION_MANAGER"] = detection_manager

    # Graceful shutdown
    def shutdown():
        logger.info("Shutting down — stopping all pipelines...")
        detection_manager.stop_all()

    atexit.register(shutdown)

    logger.info("Services initialized")
