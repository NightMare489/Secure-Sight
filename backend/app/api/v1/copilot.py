from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.schemas.copilot import CopilotRequest
from app.services.copilot_service import CopilotService

copilot_bp = Blueprint("copilot", __name__, url_prefix="/copilot")


@copilot_bp.route("/chat", methods=["POST"])
def chat():
    data = CopilotRequest.model_validate(request.get_json() or {})
    service = CopilotService(db.session, current_app.config["GEMINI_CONFIG"])
    try:
        return jsonify(service.ask(data.message, data.history))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 503
