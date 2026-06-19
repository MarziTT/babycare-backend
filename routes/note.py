"""随手记 API — 语音兜底轻量记录"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
from database import get_db

notes_bp = Blueprint("notes", __name__)


@notes_bp.route("/api/notes", methods=["GET"])
def list_notes():
    baby_id = request.args.get("baby_id", "")
    date = request.args.get("date", "")

    db = get_db()
    if date:
        rows = db.execute(
            "SELECT * FROM notes WHERE baby_id=? AND date(time)=? ORDER BY time DESC",
            (baby_id, date)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM notes WHERE baby_id=? ORDER BY time DESC LIMIT 50",
            (baby_id,)
        ).fetchall()
    records = [dict(r) for r in rows]
    db.close()
    return jsonify({"code": 0, "data": records, "message": "ok"})


@notes_bp.route("/api/notes", methods=["POST"])
def create_note():
    data = request.json
    record = {
        "id": str(uuid.uuid4()),
        "baby_id": data.get("baby_id", ""),
        "family_id": data.get("family_id", ""),
        "text": data.get("text", ""),
        "time": data.get("time", datetime.now().isoformat()),
        "recorded_by": data.get("recorded_by", ""),
        "created_at": datetime.now().isoformat(),
    }

    if not record["text"]:
        return jsonify({"code": 400, "message": "内容不能为空"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO notes (id,baby_id,family_id,text,time,recorded_by,created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (record["id"], record["baby_id"], record["family_id"],
         record["text"], record["time"], record["recorded_by"],
         record["created_at"])
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "data": record, "message": "记录成功"})


@notes_bp.route("/api/notes/<record_id>", methods=["DELETE"])
def delete_note(record_id):
    db = get_db()
    db.execute("DELETE FROM notes WHERE id=?", (record_id,))
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已删除"})
