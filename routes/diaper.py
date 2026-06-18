"""尿布记录 API"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid

diaper_bp = Blueprint("diaper", __name__)


@diaper_bp.route("/api/diaper", methods=["GET"])
def list_diaper():
    baby_id = request.args.get("baby_id", "")
    date = request.args.get("date", "")
    limit = int(request.args.get("limit", 50))
    return jsonify({"code": 0, "data": [], "message": "ok"})


@diaper_bp.route("/api/diaper", methods=["POST"])
def create_diaper():
    data = request.json
    record = {
        "id": str(uuid.uuid4()),
        "baby_id": data.get("baby_id", ""),
        "family_id": data.get("family_id", ""),
        "diaper_type": data.get("diaper_type", "wet"),
        "time": data.get("time", datetime.now().isoformat()),
        "note": data.get("note", ""),
        "recorded_by": data.get("recorded_by", ""),
        "created_at": datetime.now().isoformat(),
    }
    return jsonify({"code": 0, "data": record, "message": "记录成功"})
