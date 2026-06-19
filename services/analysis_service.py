"""AI 数据分析服务 - 喂养趋势、睡眠规律、成长曲线、接种管理"""
import json
import logging
from services.ai_service import call_llm

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """你是一个专业的育儿数据分析师。请根据以下宝宝记录数据生成分析报告。

数据：
{data_json}

请按以下 JSON 格式输出，不要输出其他内容：
{{
  "feeding_summary": {{
    "daily_avg_count": 8.5,
    "daily_avg_ml": 750,
    "longest_interval_hours": 4.2,
    "trend": "奶量稳步增长，喂养间隔逐步拉长，符合月龄发育规律"
  }},
  "sleep_summary": {{
    "daily_avg_hours": 14.5,
    "night_avg_hours": 9.0,
    "nap_count": 3,
    "trend": "夜间睡眠趋于规律，白天小睡次数减少"
  }},
  "diaper_summary": {{
    "daily_avg_count": 8,
    "wet_ratio": 0.75,
    "trend": "排便频率正常"
  }},
  "growth_summary": {{
    "latest_height_cm": 65,
    "latest_weight_kg": 7.2,
    "latest_head_circumference_cm": 42,
    "height_percentile": "P75",
    "weight_percentile": "P60",
    "trend": "身高体重均在中上水平，增长曲线平稳"
  }},
  "vaccination_summary": {{
    "total": 12,
    "completed": 10,
    "upcoming": 2,
    "trend": "接种计划按时执行，请关注下月预约"
  }},
  "medication_summary": {{
    "total_records": 3,
    "active_count": 0,
    "trend": "近期无持续用药，健康状况良好"
  }},
  "suggestions": [
    "建议将夜间喂奶间隔逐步拉长至4小时",
    "白天适当增加活动量有助于夜间睡眠延长",
    "瓶喂时可尝试120ml单次量"
  ],
  "alerts": []
}}"""


def generate_analysis(
    feeding_records: list,
    sleep_records: list,
    diaper_records: list,
    growth_records: list = None,
    vaccination_records: list = None,
    medication_records: list = None,
    notes: list = None,
    period: str = "weekly",
) -> dict:
    """生成 AI 分析报告"""
    growth_records = growth_records or []
    vaccination_records = vaccination_records or []
    medication_records = medication_records or []
    notes = notes or []

    total = (len(feeding_records) + len(sleep_records) + len(diaper_records) +
             len(growth_records) + len(vaccination_records) + len(medication_records) + len(notes))
    if total == 0:
        return {
            "empty": True,
            "message": "这段时间还没有记录，开始记录后即可生成育儿报告",
            "feeding_summary": {"daily_avg_count": 0, "daily_avg_ml": 0, "trend": "暂无数据"},
            "sleep_summary": {"daily_avg_hours": 0, "trend": "暂无数据"},
            "diaper_summary": {"daily_avg_count": 0, "wet_ratio": 0, "trend": "暂无数据"},
            "growth_summary": {"latest_height_cm": 0, "latest_weight_kg": 0, "trend": "暂无数据"},
            "vaccination_summary": {"total": 0, "completed": 0, "upcoming": 0, "trend": "暂无数据"},
            "medication_summary": {"total_records": 0, "active_count": 0, "trend": "暂无数据"},
            "suggestions": ["从今天开始记录宝宝的喂养、睡眠和尿布数据吧"],
            "alerts": [],
        }

    # 本地预计算基础统计
    local_stats = _compute_local_stats(feeding_records, sleep_records, diaper_records,
                                       growth_records, vaccination_records, medication_records)

    data = {
        "period": period,
        "feeding": feeding_records,
        "sleep": sleep_records,
        "diaper": diaper_records,
        "growth": growth_records,
        "vaccination": vaccination_records,
        "medication": medication_records,
        "notes": notes,
        "precomputed_stats": local_stats,
    }
    data_json = json.dumps(data, ensure_ascii=False, default=str)

    messages = [
        {"role": "system", "content": "你是一个精确的育儿数据分析师，只输出 JSON。"},
        {"role": "user", "content": ANALYSIS_PROMPT.format(data_json=data_json)},
    ]

    try:
        result_text = call_llm(messages, temperature=0.3)
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
        ai_result = json.loads(result_text)
        # 合并本地统计，确保前端有数据展示
        ai_result["_local_stats"] = local_stats
        return ai_result
    except Exception as e:
        logger.error(f"Analysis generation failed: {e}")
        return {
            "feeding_summary": {"trend": "数据分析暂时不可用"},
            "sleep_summary": {"trend": "数据分析暂时不可用"},
            "diaper_summary": {"trend": "数据分析暂时不可用"},
            "growth_summary": {"trend": "数据分析暂时不可用"},
            "vaccination_summary": {"trend": "数据分析暂时不可用"},
            "medication_summary": {"trend": "数据分析暂时不可用"},
            "suggestions": ["请稍后重试"],
            "alerts": [],
            "_local_stats": local_stats,
        }


def _compute_local_stats(feeding, sleep, diaper, growth, vaccination, medication) -> dict:
    """本地计算基础统计（不依赖 LLM，快速可靠）"""
    stats = {}

    # 喂养
    if feeding:
        amounts = [r.get("amount_ml", 0) for r in feeding if r.get("amount_ml")]
        durations = [r.get("duration_minutes", 0) for r in feeding if r.get("duration_minutes")]
        stats["feeding"] = {
            "count": len(feeding),
            "total_ml": sum(amounts),
            "avg_ml_per_feed": round(sum(amounts) / len(amounts)) if amounts else 0,
            "total_minutes": sum(durations),
            "avg_minutes": round(sum(durations) / len(durations)) if durations else 0,
        }

    # 睡眠
    if sleep:
        durations = [r.get("duration_minutes", 0) for r in sleep if r.get("duration_minutes")]
        stats["sleep"] = {
            "count": len(sleep),
            "total_hours": round(sum(durations) / 60, 1),
            "avg_hours_per_sleep": round(sum(durations) / len(durations) / 60, 1) if durations else 0,
        }

    # 尿布
    if diaper:
        types = [r.get("diaper_type", "") for r in diaper]
        stats["diaper"] = {
            "count": len(diaper),
            "wet_count": types.count("wet"),
            "dry_count": types.count("dry"),
            "mixed_count": types.count("mixed"),
        }

    # 成长
    if growth:
        heights = [(r.get("height_cm") or r.get("height")) for r in growth]
        heights = [h for h in heights if h is not None]
        weights = [(r.get("weight_kg") or r.get("weight")) for r in growth]
        weights = [w for w in weights if w is not None]
        hc_list = [(r.get("head_circumference_cm") or r.get("head_circumference")) for r in growth]
        hc_list = [h for h in hc_list if h is not None]
        stats["growth"] = {
            "count": len(growth),
            "latest_height_cm": heights[-1] if heights else 0,
            "latest_weight_kg": weights[-1] if weights else 0,
            "latest_head_circumference_cm": hc_list[-1] if hc_list else 0,
            "height_change_cm": round(heights[-1] - heights[0], 1) if len(heights) > 1 else 0,
            "weight_change_kg": round(weights[-1] - weights[0], 1) if len(weights) > 1 else 0,
        }

    # 疫苗
    if vaccination:
        statuses = [r.get("status", "") for r in vaccination]
        stats["vaccination"] = {
            "total": len(vaccination),
            "completed": statuses.count("completed"),
            "upcoming": statuses.count("upcoming"),
            "skipped": statuses.count("skipped"),
        }

    # 用药
    if medication:
        stats["medication"] = {
            "total_records": len(medication),
            "medicines": list(set(r.get("medicine_name", "") for r in medication if r.get("medicine_name"))),
        }

    return stats


def compute_basic_stats(records: list, record_type: str) -> dict:
    """本地计算基础统计（不依赖 LLM）"""
    if not records:
        return {"count": 0, "message": "暂无记录"}

    stats = {"count": len(records)}

    if record_type == "feeding":
        durations = [r.get("duration_minutes", 0) for r in records if r.get("duration_minutes")]
        amounts = [r.get("amount_ml", 0) for r in records if r.get("amount_ml")]
        if durations:
            stats["avg_duration"] = round(sum(durations) / len(durations), 1)
            stats["total_minutes"] = sum(durations)
        if amounts:
            stats["total_ml"] = sum(amounts)
            stats["avg_ml"] = round(sum(amounts) / len(amounts), 1)

    elif record_type == "sleep":
        durations = [r.get("duration_minutes", 0) for r in records if r.get("duration_minutes")]
        if durations:
            stats["total_hours"] = round(sum(durations) / 60, 1)
            stats["avg_hours"] = round(sum(durations) / len(durations) / 60, 1)

    elif record_type == "diaper":
        types = [r.get("diaper_type", "") for r in records]
        stats["wet_count"] = types.count("wet")
        stats["dry_count"] = types.count("dry")
        stats["mixed_count"] = types.count("mixed")

    return stats
