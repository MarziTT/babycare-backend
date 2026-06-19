"""睡眠记录 API"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
from database import get_db

sleep_bp = Blueprint("sleep", __name__)


@sleep_bp.route("/api/sleep", methods=["GET"])
def list_sleep():
    baby_id = request.args.get("baby_id", "")
    date = request.args.get("date", "")
    limit = int(request.args.get("limit", 50))

    db = get_db()
    if date:
        rows = db.execute(
            "SELECT * FROM sleep WHERE baby_id=? AND date(start_time)=? ORDER BY start_time DESC LIMIT ?",
            (baby_id, date, limit)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM sleep WHERE baby_id=? ORDER BY start_time DESC LIMIT ?",
            (baby_id, limit)
        ).fetchall()
    records = [dict(r) for r in rows]
    db.close()
    return jsonify({"code": 0, "data": records, "message": "ok"})


@sleep_bp.route("/api/sleep", methods=["POST"])
def create_sleep():
    data = request.json
    baby_id = data.get("baby_id", "")
    start_time = data.get("start_time", datetime.now().isoformat())
    recorded_by = data.get("recorded_by", "")

    db = get_db()

    # 去重：查询今天同 baby_id、start_time 在 5 分钟内的记录
    today = datetime.now().strftime("%Y-%m-%d")
    dup_rows = db.execute(
        "SELECT * FROM sleep WHERE baby_id=? AND date(start_time)=? "
        "AND ABS(strftime('%s', start_time) - strftime('%s', ?)) < 300 "
        "ORDER BY start_time ASC LIMIT 1",
        (baby_id, today, start_time)
    ).fetchall()

    if dup_rows:
        dup = dict(dup_rows[0])
        if dup.get("recorded_by") != recorded_by:
            try:
                dup_time = datetime.fromisoformat(dup["start_time"])
                cur_time = datetime.fromisoformat(start_time)
                diff_seconds = abs((cur_time - dup_time).total_seconds())
                if diff_seconds < 60:
                    diff_str = str(int(diff_seconds)) + "秒"
                else:
                    diff_str = str(int(diff_seconds // 60)) + "分钟"
            except Exception:
                diff_str = "5分钟"
            db.close()
            return jsonify({"code": 409, "message": "该记录已在" + diff_str + "前由其他成员记录过了"})
        else:
            db.close()
            return jsonify({"code": 409, "message": "请勿重复提交"})

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

    db.execute(
        "INSERT INTO sleep (id,baby_id,family_id,start_time,end_time,duration_minutes,note,recorded_by,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (record["id"], record["baby_id"], record["family_id"], record["start_time"],
         record["end_time"], record["duration_minutes"], record["note"],
         record["recorded_by"], record["created_at"])
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "data": record, "message": "记录成功"})


@sleep_bp.route("/api/sleep/<record_id>", methods=["DELETE"])
def delete_sleep(record_id):
    db = get_db()
    db.execute("DELETE FROM sleep WHERE id=?", (record_id,))
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已删除"})
