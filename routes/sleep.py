"""睡眠记录 API"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
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
    start_time = data.get("start_time", datetime.now(CST).isoformat())
    end_time = data.get("end_time", "")
    recorded_by = data.get("recorded_by", "")

    db = get_db()

    # 校验：开始时间和结束时间均不能超过当前时间
    now_cst = datetime.now(CST)
    st = None
    et = None
    if start_time:
        st = datetime.fromisoformat(start_time).replace(tzinfo=CST)
        if st > now_cst:
            db.close()
            return jsonify({"code": 400, "message": "开始时间不能是未来时间"}), 400
    if end_time:
        et = datetime.fromisoformat(end_time).replace(tzinfo=CST)
        if et > now_cst:
            db.close()
            return jsonify({"code": 400, "message": "结束时间不能是未来时间"}), 400
    # 校验：开始时间不能晚于结束时间
    if st and et and st >= et:
        db.close()
        return jsonify({"code": 400, "message": "开始时间不能晚于结束时间"}), 400

    # 去重：同一 start_time 精确匹配（时间戳误差 3 秒内），防双击重复提交
    today = datetime.now(CST).strftime("%Y-%m-%d")
    dup_rows = db.execute(
        "SELECT * FROM sleep WHERE baby_id=? AND date(start_time)=? "
        "AND ABS(strftime('%s', start_time) - strftime('%s', ?)) < 3 "
        "ORDER BY start_time ASC LIMIT 1",
        (baby_id, today, start_time)
    ).fetchall()

    if dup_rows:
        db.close()
        return jsonify({"code": 409, "message": "请勿重复提交"})

    record = {
        "id": str(uuid.uuid4()),
        "baby_id": data.get("baby_id", ""),
        "family_id": data.get("family_id", ""),
        "start_time": data.get("start_time", datetime.now(CST).isoformat()),
        "end_time": data.get("end_time", ""),
        "duration_minutes": data.get("duration_minutes", 0),
        "note": data.get("note", ""),
        "recorded_by": data.get("recorded_by", ""),
        "recorded_by_name": data.get("recorded_by_name", ""),
        "recorded_by_avatar": data.get("recorded_by_avatar", ""),
        "created_at": datetime.now(CST).isoformat(),
    }

    db.execute(
        "INSERT INTO sleep (id,baby_id,family_id,start_time,end_time,duration_minutes,note,recorded_by,recorded_by_name,recorded_by_avatar,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (record["id"], record["baby_id"], record["family_id"], record["start_time"],
         record["end_time"], record["duration_minutes"], record["note"],
         record["recorded_by"], record["recorded_by_name"], record["recorded_by_avatar"], record["created_at"])
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "data": record, "message": "记录成功"})


@sleep_bp.route("/api/sleep/<record_id>", methods=["GET"])
def get_sleep(record_id):
    db = get_db()
    row = db.execute("SELECT * FROM sleep WHERE id=?", (record_id,)).fetchone()
    db.close()
    if not row:
        return jsonify({"code": 404, "message": "记录不存在"})
    record = dict(row)
    return jsonify({"code": 0, "data": record, "message": "ok"})


@sleep_bp.route("/api/sleep/<record_id>", methods=["PUT"])
def update_sleep(record_id):
    data = request.json
    db = get_db()
    db.execute(
        "UPDATE sleep SET start_time=?, end_time=?, duration_minutes=?, note=? WHERE id=?",
        (data.get("start_time", ""), data.get("end_time", ""),
         data.get("duration_minutes", 0), data.get("note", ""), record_id)
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已更新"})


@sleep_bp.route("/api/sleep/<record_id>", methods=["DELETE"])
def delete_sleep(record_id):
    db = get_db()
    db.execute("DELETE FROM sleep WHERE id=?", (record_id,))
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已删除"})
