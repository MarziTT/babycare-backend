"""用药记录 API"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
import uuid
from database import get_db

medication_bp = Blueprint("medication", __name__)


@medication_bp.route("/api/medication", methods=["GET"])
def list_medication():
    baby_id = request.args.get("baby_id", "")
    date = request.args.get("date", "")

    db = get_db()
    if date:
        rows = db.execute(
            "SELECT * FROM medication WHERE baby_id=? AND date(start_time)=? ORDER BY start_time DESC",
            (baby_id, date)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM medication WHERE baby_id=? ORDER BY start_time DESC",
            (baby_id,)
        ).fetchall()
    records = [dict(r) for r in rows]
    db.close()
    return jsonify({"code": 0, "data": records, "message": "ok"})


@medication_bp.route("/api/medication", methods=["POST"])
def create_medication():
    data = request.json
    record = {
        "id": str(uuid.uuid4()),
        "baby_id": data.get("baby_id", ""),
        "family_id": data.get("family_id", ""),
        "medicine_name": data.get("medicine_name", ""),
        "dosage": data.get("dosage", ""),
        "unit": data.get("unit", ""),
        "start_time": data.get("start_time", datetime.now(CST).isoformat()),
        "end_time": data.get("end_time", ""),
        "frequency": data.get("frequency", ""),
        "note": data.get("note", ""),
        "recorded_by": data.get("recorded_by", ""),
        "recorded_by_name": data.get("recorded_by_name", ""),
        "recorded_by_avatar": data.get("recorded_by_avatar", ""),
        "created_at": datetime.now(CST).isoformat(),
    }

    if not record["medicine_name"]:
        return jsonify({"code": 400, "message": "药品名称不能为空"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO medication (id,baby_id,family_id,medicine_name,dosage,unit,start_time,end_time,frequency,note,recorded_by,recorded_by_name,recorded_by_avatar,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (record["id"], record["baby_id"], record["family_id"], record["medicine_name"],
         record["dosage"], record["unit"], record["start_time"], record["end_time"],
         record["frequency"], record["note"], record["recorded_by"],
         record["recorded_by_name"], record["recorded_by_avatar"], record["created_at"])
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "data": record, "message": "记录成功"})


@medication_bp.route("/api/medication/<record_id>", methods=["DELETE"])
def delete_medication(record_id):
    db = get_db()
    db.execute("DELETE FROM medication WHERE id=?", (record_id,))
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已删除"})
