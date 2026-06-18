"""尿布记录 API"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
from database import get_db

diaper_bp = Blueprint("diaper", __name__)


@diaper_bp.route("/api/diaper", methods=["GET"])
def list_diaper():
    baby_id = request.args.get("baby_id", "")
    date = request.args.get("date", "")
    limit = int(request.args.get("limit", 50))

    db = get_db()
    if date:
        rows = db.execute(
            "SELECT * FROM diaper WHERE baby_id=? AND date(time)=? ORDER BY time DESC LIMIT ?",
            (baby_id, date, limit)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM diaper WHERE baby_id=? ORDER BY time DESC LIMIT ?",
            (baby_id, limit)
        ).fetchall()
    records = [dict(r) for r in rows]
    db.close()
    return jsonify({"code": 0, "data": records, "message": "ok"})


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

    db = get_db()
    db.execute(
        "INSERT INTO diaper (id,baby_id,family_id,diaper_type,time,note,recorded_by,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (record["id"], record["baby_id"], record["family_id"], record["diaper_type"],
         record["time"], record["note"], record["recorded_by"], record["created_at"])
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "data": record, "message": "记录成功"})


@diaper_bp.route("/api/diaper/<record_id>", methods=["DELETE"])
def delete_diaper(record_id):
    db = get_db()
    db.execute("DELETE FROM diaper WHERE id=?", (record_id,))
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已删除"})
