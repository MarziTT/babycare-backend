"""睡眠记录 API"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid

sleep_bp = Blueprint("sleep", __name__)


@sleep_bp.route("/api/sleep", methods=["GET"])
def list_sleep():
    baby_id = request.args.get("baby_id", "")
    date = request.args.get("date", "")
    limit = int(request.args.get("limit", 50))
    return jsonify({"code": 0, "data": [], "message": "ok"})


@sleep_bp.route("/api/sleep", methods=["POST"])
def create_sleep():
    data = request.json
    record = {
        "id": str(uuid.uuid4()),
        "baby_id": data.get("baby_id", ""),
        "family_id": data.get("family_id", ""),
        "start_time": data.get("start_time", datetime.now().isoformat()),
        "end_time": data.get("end_time", ""),
        "duration_minutes": data.get("duration_minutes", 0),
        "note": data.get("note", ""),
        "recorded_by": data.get("recorded_by", ""),
        "created_at": datetime.now().isoformat(),
    }
    return jsonify({"code": 0, "data": record, "message": "记录成功"})
