"""疫苗接种提醒 API"""
from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
import uuid
from database import get_db

vaccination_bp = Blueprint("vaccination", __name__)


@vaccination_bp.route("/api/vaccination", methods=["GET"])
def list_vaccination():
    baby_id = request.args.get("baby_id", "")
    status = request.args.get("status", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    db = get_db()
    query = "SELECT * FROM vaccination WHERE baby_id=?"
    params = [baby_id]

    if status:
        query += " AND status=?"
        params.append(status)
    if date_from:
        query += " AND scheduled_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND scheduled_date <= ?"
        params.append(date_to)

    query += " ORDER BY scheduled_date ASC"
    rows = db.execute(query, params).fetchall()
    records = [dict(r) for r in rows]
    db.close()
    return jsonify({"code": 0, "data": records, "message": "ok"})


@vaccination_bp.route("/api/vaccination", methods=["POST"])
def create_vaccination():
    data = request.json
    record = {
        "id": str(uuid.uuid4()),
        "baby_id": data.get("baby_id", ""),
        "family_id": data.get("family_id", ""),
        "vaccine_name": data.get("vaccine_name", ""),
        "scheduled_date": data.get("scheduled_date", ""),
        "status": data.get("status", "upcoming"),
        "actual_date": data.get("actual_date", ""),
        "note": data.get("note", ""),
        "recorded_by": data.get("recorded_by", ""),
        "recorded_by_name": data.get("recorded_by_name", ""),
        "recorded_by_avatar": data.get("recorded_by_avatar", ""),
        "created_at": datetime.now(CST).isoformat(),
    }

    if not record["vaccine_name"] or not record["scheduled_date"]:
        return jsonify({"code": 400, "message": "疫苗名称和计划日期不能为空"}), 400

    # 校验：必须已创建家庭（strip 防止空白字符绕过）
    if not (record.get("family_id") or "").strip():
        return jsonify({"code": 400, "message": "请先创建家庭信息"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO vaccination (id,baby_id,family_id,vaccine_name,scheduled_date,status,actual_date,note,recorded_by,recorded_by_name,recorded_by_avatar,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (record["id"], record["baby_id"], record["family_id"], record["vaccine_name"],
         record["scheduled_date"], record["status"], record["actual_date"],
         record["note"], record["recorded_by"], record["recorded_by_name"], record["recorded_by_avatar"], record["created_at"])
    )
    db.commit()
    db.close()
    return jsonify({"code": 0, "data": record, "message": "添加成功"})


@vaccination_bp.route("/api/vaccination/<record_id>", methods=["PUT"])
def update_vaccination(record_id):
    data = request.json
    db = get_db()

    # 只更新允许的字段
    updates = []
    params = []

    if "status" in data:
        updates.append("status=?")
        params.append(data["status"])
    if "actual_date" in data:
        updates.append("actual_date=?")
        params.append(data["actual_date"])
    if "note" in data:
        updates.append("note=?")
        params.append(data["note"])

    if not updates:
        db.close()
        return jsonify({"code": 400, "message": "没有可更新的字段"}), 400

    params.append(record_id)
    sql = f"UPDATE vaccination SET {', '.join(updates)} WHERE id=?"
    db.execute(sql, params)
    db.commit()

    # 返回更新后的记录
    row = db.execute("SELECT * FROM vaccination WHERE id=?", (record_id,)).fetchone()
    db.close()

    if row is None:
        return jsonify({"code": 404, "message": "记录不存在"}), 404
    return jsonify({"code": 0, "data": dict(row), "message": "更新成功"})


@vaccination_bp.route("/api/vaccination/<record_id>", methods=["DELETE"])
def delete_vaccination(record_id):
    db = get_db()
    db.execute("DELETE FROM vaccination WHERE id=?", (record_id,))
    db.commit()
    db.close()
    return jsonify({"code": 0, "message": "已删除"})
