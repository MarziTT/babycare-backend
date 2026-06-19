"""AI 数据分析服务 - 喂养趋势、睡眠规律、异常检测"""
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
    period: str = "weekly",
) -> dict:
    """生成 AI 分析报告"""
    # 空记录检查：没有任何记录时直接返回友好提示
    total = len(feeding_records) + len(sleep_records) + len(diaper_records)
    if total == 0:
        return {
            "empty": True,
            "message": "本周还没有记录，开始记录后即可生成育儿报告",
            "feeding_summary": {"daily_avg_count": 0, "daily_avg_ml": 0, "trend": "暂无数据"},
            "sleep_summary": {"daily_avg_hours": 0, "trend": "暂无数据"},
            "diaper_summary": {"daily_avg_count": 0, "wet_ratio": 0, "trend": "暂无数据"},
            "suggestions": ["从今天开始记录宝宝的喂养、睡眠和尿布数据吧"],
            "alerts": [],
        }

    data = {
        "period": period,
        "feeding": feeding_records,
        "sleep": sleep_records,
        "diaper": diaper_records,
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
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"Analysis generation failed: {e}")
        return {
            "feeding_summary": {"trend": "数据分析暂时不可用"},
            "sleep_summary": {"trend": "数据分析暂时不可用"},
            "diaper_summary": {"trend": "数据分析暂时不可用"},
            "suggestions": ["请稍后重试"],
            "alerts": [],
        }


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
