"""喂奶记录 API"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
from database import get_db

feeding_bp = Blueprint("feeding", __name__)


@feeding_bp.route("/api/feeding", methods=["GET"])
def list_feeding():
    baby_id = request.args.get("baby_id", "")
    date = request.args.get("date", "")
    limit = int(request.args.get("limit", 50))

    db = get_db()
    if date:
        rows = db.execute(
            "SELECT * FROM feeding WHERE baby_id=? AND date(start_time)=? ORDER BY start_time DESC LIMIT ?",
            (baby_id, date, limit)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM feeding WHERE baby_id=? ORDER BY start_time DESC LIMIT ?",
            (baby_id, limit)
        ).fetchall()
    records = [dict(r) for r in rows]
    db.close()
    return jsonify({"code": 0, "data": records, "message": "ok"})


@feeding_bp.route("/api/feeding", methods=["POST"])
def create_feeding():
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

    db = get_db()
    db.execute(
        "INSERT INTO feeding (id,baby_id,family_id,feed_type,start_time,end_time,duration_minutes,amount_ml,note,recorded_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (record["id"], record["baby_id"], record["family_id"], record["feed_type"],
         record["start_time"], record["end_time"], record["duration_minutes"],
         record["amount_ml"], record["note"], record["recorded_by"], record["created_at"])
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "data": record, "message": "记录成功"})


@feeding_bp.route("/api/feeding/<record_id>", methods=["DELETE"])
def delete_feeding(record_id):
    db = get_db()
    db.execute("DELETE FROM feeding WHERE id=?", (record_id,))
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已删除"})


@feeding_bp.route("/api/feeding/today", methods=["GET"])
def today_summary():
    baby_id = request.args.get("baby_id", "")
    today = datetime.now().strftime("%Y-%m-%d")

    db = get_db()
    rows = db.execute(
        "SELECT * FROM feeding WHERE baby_id=? AND date(start_time)=? ORDER BY start_time DESC",
        (baby_id, today)
    ).fetchall()
    db.close()

    records = [dict(r) for r in rows]
    total_count = len(records)
    total_duration = sum(r["duration_minutes"] for r in records)
    total_amount = sum(r["amount_ml"] for r in records)
    last_feed = records[0]["start_time"] if records else None

    return jsonify({
        "code": 0,
        "data": {
            "total_count": total_count,
            "total_duration_minutes": total_duration,
            "total_amount_ml": total_amount,
            "last_feed_time": last_feed,
            "next_estimated": None,
        }
    })
