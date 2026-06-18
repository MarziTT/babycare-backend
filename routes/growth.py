"""成长记录 API"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
from database import get_db

growth_bp = Blueprint("growth", __name__)


@growth_bp.route("/api/growth", methods=["GET"])
def list_growth():
    baby_id = request.args.get("baby_id", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    db = get_db()
    if date_from and date_to:
        rows = db.execute(
            "SELECT * FROM growth WHERE baby_id=? AND record_date BETWEEN ? AND ? ORDER BY record_date DESC",
            (baby_id, date_from, date_to)
        ).fetchall()
    elif date_from:
        rows = db.execute(
            "SELECT * FROM growth WHERE baby_id=? AND record_date >= ? ORDER BY record_date DESC",
            (baby_id, date_from)
        ).fetchall()
    elif date_to:
        rows = db.execute(
            "SELECT * FROM growth WHERE baby_id=? AND record_date <= ? ORDER BY record_date DESC",
            (baby_id, date_to)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM growth WHERE baby_id=? ORDER BY record_date DESC",
            (baby_id,)
        ).fetchall()
    records = [dict(r) for r in rows]
    db.close()
    return jsonify({"code": 0, "data": records, "message": "ok"})


@growth_bp.route("/api/growth", methods=["POST"])
def create_growth():
    data = request.json
    record = {
        "id": str(uuid.uuid4()),
        "baby_id": data.get("baby_id", ""),
        "family_id": data.get("family_id", ""),
        "record_date": data.get("record_date", datetime.now().strftime("%Y-%m-%d")),
        "height_cm": data.get("height_cm"),
        "weight_kg": data.get("weight_kg"),
        "head_circumference_cm": data.get("head_circumference_cm"),
        "note": data.get("note", ""),
        "recorded_by": data.get("recorded_by", ""),
        "created_at": datetime.now().isoformat(),
    }

    db = get_db()
    db.execute(
        "INSERT INTO growth (id,baby_id,family_id,record_date,height_cm,weight_kg,head_circumference_cm,note,recorded_by,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (record["id"], record["baby_id"], record["family_id"], record["record_date"],
         record["height_cm"], record["weight_kg"], record["head_circumference_cm"],
         record["note"], record["recorded_by"], record["created_at"])
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "data": record, "message": "记录成功"})


@growth_bp.route("/api/growth/<record_id>", methods=["DELETE"])
def delete_growth(record_id):
    db = get_db()
    db.execute("DELETE FROM growth WHERE id=?", (record_id,))
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已删除"})
