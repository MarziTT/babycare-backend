"""喂奶记录 API"""
import logging
from flask import Blueprint, request, jsonify
from datetime import datetime
import uuid
from database import get_db

logger = logging.getLogger(__name__)

feeding_bp = Blueprint("feeding", __name__)


@feeding_bp.route("/api/feeding", methods=["GET"])
def list_feeding():
    baby_id = request.args.get("baby_id", "")
    family_id = request.args.get("family_id", "")
    date = request.args.get("date", "")
    limit = int(request.args.get("limit", 50))

    db = get_db()
    if family_id and baby_id != family_id:
        # Backward compat: also include old records where baby_id = family_id
        if date:
            rows = db.execute(
                "SELECT * FROM feeding WHERE (baby_id=? OR baby_id=?) AND date(start_time)=? ORDER BY start_time DESC LIMIT ?",
                (baby_id, family_id, date, limit)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM feeding WHERE (baby_id=? OR baby_id=?) ORDER BY start_time DESC LIMIT ?",
                (baby_id, family_id, limit)
            ).fetchall()
    elif date:
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
    baby_id = data.get("baby_id", "")
    feed_type = data.get("feed_type", "left")
    start_time = data.get("start_time", datetime.now().isoformat())
    recorded_by = data.get("recorded_by", "")

    db = get_db()

    # 去重：查询今天同 baby_id、同 feed_type、start_time 在 5 分钟内的记录
    today = datetime.now().strftime("%Y-%m-%d")
    dup_rows = db.execute(
        "SELECT * FROM feeding WHERE baby_id=? AND feed_type=? AND date(start_time)=? "
        "AND ABS(strftime('%s', start_time) - strftime('%s', ?)) < 300 "
        "ORDER BY start_time ASC LIMIT 1",
        (baby_id, feed_type, today, start_time)
    ).fetchall()

    if dup_rows:
        dup = dict(dup_rows[0])
        if dup.get("recorded_by") != recorded_by:
            # 计算时间差
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
        "feed_type": data.get("feed_type", "left"),
        "start_time": data.get("start_time", datetime.now().isoformat()),
        "end_time": data.get("end_time", ""),
        "duration_minutes": data.get("duration_minutes", 0),
        "amount_ml": data.get("amount_ml", 0),
        "note": data.get("note", ""),
        "recorded_by": data.get("recorded_by", ""),
        "recorded_by_name": data.get("recorded_by_name", ""),
        "recorded_by_avatar": data.get("recorded_by_avatar", ""),
        "created_at": datetime.now().isoformat(),
    }

    db.execute(
        "INSERT INTO feeding (id,baby_id,family_id,feed_type,start_time,end_time,duration_minutes,amount_ml,note,recorded_by,recorded_by_name,recorded_by_avatar,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (record["id"], record["baby_id"], record["family_id"], record["feed_type"],
         record["start_time"], record["end_time"], record["duration_minutes"],
         record["amount_ml"], record["note"], record["recorded_by"],
         record["recorded_by_name"], record["recorded_by_avatar"], record["created_at"])
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "data": record, "message": "记录成功"})


@feeding_bp.route("/api/feeding/<record_id>", methods=["GET"])
def get_feeding(record_id):
    db = get_db()
    row = db.execute("SELECT * FROM feeding WHERE id=?", (record_id,)).fetchone()
    db.close()
    if not row:
        return jsonify({"code": 404, "message": "记录不存在"})
    record = dict(row)
    return jsonify({"code": 0, "data": record, "message": "ok"})


@feeding_bp.route("/api/feeding/<record_id>", methods=["PUT"])
def update_feeding(record_id):
    data = request.json
    logger.info(f"[DEBUG-PUT] record_id={record_id}")
    logger.info(f"[DEBUG-PUT] raw json keys: {list(data.keys()) if data else 'None'}")
    logger.info(f"[DEBUG-PUT] note={repr(data.get('note', ''))}")
    logger.info(f"[DEBUG-PUT] full data: {data}")
    db = get_db()
    cursor = db.execute(
        "UPDATE feeding SET feed_type=?, start_time=?, end_time=?, duration_minutes=?, amount_ml=?, note=? WHERE id=?",
        (data.get("feed_type", "left"), data.get("start_time", ""), data.get("end_time", ""),
         data.get("duration_minutes", 0), data.get("amount_ml", 0), data.get("note", ""), record_id)
    )
    logger.info(f"[DEBUG-PUT] rowcount={cursor.rowcount}")
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已更新"})


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
