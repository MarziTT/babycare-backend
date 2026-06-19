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
    baby_id = data.get("baby_id", "")
    diaper_type = data.get("diaper_type", "wet")
    time_val = data.get("time", datetime.now().isoformat())
    recorded_by = data.get("recorded_by", "")

    db = get_db()

    # 去重：查询今天同 baby_id、同 diaper_type、time 在 5 分钟内的记录
    today = datetime.now().strftime("%Y-%m-%d")
    dup_rows = db.execute(
        "SELECT * FROM diaper WHERE baby_id=? AND diaper_type=? AND date(time)=? "
        "AND ABS(strftime('%s', time) - strftime('%s', ?)) < 300 "
        "ORDER BY time ASC LIMIT 1",
        (baby_id, diaper_type, today, time_val)
    ).fetchall()

    if dup_rows:
        dup = dict(dup_rows[0])
        if dup.get("recorded_by") != recorded_by:
            try:
                dup_time = datetime.fromisoformat(dup["time"])
                cur_time = datetime.fromisoformat(time_val)
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
        "diaper_type": data.get("diaper_type", "wet"),
        "time": data.get("time", datetime.now().isoformat()),
        "note": data.get("note", ""),
        "recorded_by": data.get("recorded_by", ""),
        "created_at": datetime.now().isoformat(),
    }

    db.execute(
        "INSERT INTO diaper (id,baby_id,family_id,diaper_type,time,note,recorded_by,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (record["id"], record["baby_id"], record["family_id"], record["diaper_type"],
         record["time"], record["note"], record["recorded_by"], record["created_at"])
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "data": record, "message": "记录成功"})


@diaper_bp.route("/api/diaper/<record_id>", methods=["GET"])
def get_diaper(record_id):
    db = get_db()
    row = db.execute("SELECT * FROM diaper WHERE id=?", (record_id,)).fetchone()
    db.close()
    if not row:
        return jsonify({"code": 404, "message": "记录不存在"})
    record = dict(row)
    return jsonify({"code": 0, "data": record, "message": "ok"})


@diaper_bp.route("/api/diaper/<record_id>", methods=["PUT"])
def update_diaper(record_id):
    data = request.json
    db = get_db()
    db.execute(
        "UPDATE diaper SET diaper_type=?, time=?, note=? WHERE id=?",
        (data.get("diaper_type", "wet"), data.get("time", ""), data.get("note", ""), record_id)
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已更新"})


@diaper_bp.route("/api/diaper/<record_id>", methods=["DELETE"])
def delete_diaper(record_id):
    db = get_db()
    db.execute("DELETE FROM diaper WHERE id=?", (record_id,))
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已删除"})
