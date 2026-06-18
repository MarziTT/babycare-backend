"""喂奶记录 API"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid

feeding_bp = Blueprint("feeding", __name__)


@feeding_bp.route("/api/feeding", methods=["GET"])
def list_feeding():
    """获取喂奶记录列表"""
    baby_id = request.args.get("baby_id", "")
    date = request.args.get("date", "")  # YYYY-MM-DD
    limit = int(request.args.get("limit", 50))

    # TODO: 从微信云数据库查询
    # db.collection('feeding').where({baby_id, date}).order_by('start_time','desc').limit(limit).get()
    return jsonify({"code": 0, "data": [], "message": "ok"})


@feeding_bp.route("/api/feeding", methods=["POST"])
def create_feeding():
    """创建喂奶记录"""
    data = request.json
    record = {
        "id": str(uuid.uuid4()),
        "baby_id": data.get("baby_id", ""),
        "family_id": data.get("family_id", ""),
        "feed_type": data.get("feed_type", "left"),
        "start_time": data.get("start_time", datetime.now().isoformat()),
        "end_time": data.get("end_time", ""),
        "duration_minutes": data.get("duration_minutes", 0),
        "amount_ml": data.get("amount_ml", 0),
        "note": data.get("note", ""),
        "recorded_by": data.get("recorded_by", ""),
        "created_at": datetime.now().isoformat(),
    }
    # TODO: 写入微信云数据库
    return jsonify({"code": 0, "data": record, "message": "记录成功"})


@feeding_bp.route("/api/feeding/<record_id>", methods=["DELETE"])
def delete_feeding(record_id):
    """删除喂奶记录"""
    # TODO: 从云数据库删除
    return jsonify({"code": 0, "message": "已删除"})


@feeding_bp.route("/api/feeding/today", methods=["GET"])
def today_summary():
    """今日喂养概览"""
    baby_id = request.args.get("baby_id", "")
    # TODO: 查询今日记录并计算统计
    return jsonify({
        "code": 0,
        "data": {
            "total_count": 0,
            "total_duration_minutes": 0,
            "total_amount_ml": 0,
            "last_feed_time": None,
            "next_estimated": None,
        }
    })
