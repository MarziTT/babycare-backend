"""数据分析 API"""
from flask import Blueprint, request, jsonify
from services.analysis_service import generate_analysis, compute_basic_stats

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/api/analysis/report", methods=["POST"])
def get_analysis_report():
    """生成 AI 分析报告"""
    data = request.json
    baby_id = data.get("baby_id", "")
    period = data.get("period", "weekly")
    feeding_records = data.get("feeding", [])
    sleep_records = data.get("sleep", [])
    diaper_records = data.get("diaper", [])

    if not any([feeding_records, sleep_records, diaper_records]):
        return jsonify({"code": 400, "message": "请提供至少一种记录数据"}), 400

    report = generate_analysis(feeding_records, sleep_records, diaper_records, period)
    return jsonify({"code": 0, "data": report, "message": "ok"})


@analysis_bp.route("/api/analysis/stats", methods=["GET"])
def get_basic_stats():
    """获取基础统计（不依赖 LLM，速度快）"""
    baby_id = request.args.get("baby_id", "")
    record_type = request.args.get("type", "feeding")

    # TODO: 从云数据库查询近期记录
    records = []
    stats = compute_basic_stats(records, record_type)
    return jsonify({"code": 0, "data": stats, "message": "ok"})
