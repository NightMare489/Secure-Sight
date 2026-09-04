"""
Application Entry Point.

Run this file to start the Flask development server with SocketIO support.

Usage:
    python run.py
"""

from pathlib import Path

from dotenv import load_dotenv

from app.config import AppConfig
from app.extensions import socketio
from app.main import create_app

if __name__ == "__main__":
    load_dotenv(Path(__file__).with_name(".env"))
    config = AppConfig.from_env()
    app = create_app(config)

    print(f"\n{'='*60}")
    print(f"  Secure Sight — Zone-Based Person Detection System")
    print(f"  Server: http://{config.host}:{config.port}")
    print(f"  API:    http://{config.host}:{config.port}/api/v1")
    print(f"  Debug:  {config.debug}")
    print(f"{'='*60}\n")

    socketio.run(
        app,
        host=config.host,
        port=config.port,
        debug=config.debug,
        allow_unsafe_werkzeug=True,
    )
