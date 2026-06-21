"""成长记录 API"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
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
        "record_date": data.get("record_date", datetime.now(CST).strftime("%Y-%m-%d")),
        "height_cm": data.get("height_cm"),
        "weight_kg": data.get("weight_kg"),
        "head_circumference_cm": data.get("head_circumference_cm"),
        "note": data.get("note", ""),
        "recorded_by": data.get("recorded_by", ""),
        "recorded_by_name": data.get("recorded_by_name", ""),
        "recorded_by_avatar": data.get("recorded_by_avatar", ""),
        "created_at": datetime.now(CST).isoformat(),
    }

    # 校验：必须已创建家庭
    if not record["family_id"]:
        return jsonify({"code": 400, "message": "请先创建家庭信息"}), 400

    # 校验：记录日期不能是未来
    if record["record_date"]:
        rd = datetime.strptime(record["record_date"], "%Y-%m-%d").replace(tzinfo=CST)
        if rd > datetime.now(CST):
            return jsonify({"code": 400, "message": "记录日期不能是未来日期"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO growth (id,baby_id,family_id,record_date,height_cm,weight_kg,head_circumference_cm,note,recorded_by,recorded_by_name,recorded_by_avatar,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (record["id"], record["baby_id"], record["family_id"], record["record_date"],
         record["height_cm"], record["weight_kg"], record["head_circumference_cm"],
         record["note"], record["recorded_by"], record["recorded_by_name"], record["recorded_by_avatar"], record["created_at"])
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
