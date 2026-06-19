"""AI 服务封装 - LLM 调用、意图解析、语音转文字（同步版本）"""
import json
import logging
import re
from datetime import datetime, timedelta
import httpx
from config import Config

logger = logging.getLogger(__name__)


def _parse_time(text: str) -> str | None:
    """从文本中提取时间点，返回 ISO 字符串。
    
    支持：上午9点、下午4点、晚上8点、凌晨3点、6点半、8点20分、刚刚/现在
    智能回退：如果解析时间在未来（如凌晨说"下午4点"），自动回退一天。
    """
    now = datetime.now()

    # 时间模式：(前缀, 正则, 小时计算函数)
    patterns = [
        (r'(凌晨|早上|早晨)\s*(\d{1,2})\s*点', lambda h: h % 24),
        (r'上午\s*(\d{1,2})\s*点',     lambda h: 0 if h == 12 else h),
        (r'中午\s*(\d{1,2})\s*点',     lambda h: 12 if h == 12 else 12 + h),
        (r'下午\s*(\d{1,2})\s*点',     lambda h: 12 if h == 12 else 12 + h),
        (r'傍晚\s*(\d{1,2})\s*点',     lambda h: min(12 + h, 18)),
        (r'晚上\s*(\d{1,2})\s*点',     lambda h: 12 + h),
        (r'夜里\s*(\d{1,2})\s*点',     lambda h: min(12 + h, 23)),
        (r'(\d{1,2})\s*点',            lambda h: h),  # 纯数字"9点"默认上午
    ]

    hour = None
    for pattern, fn in patterns:
        m = re.search(pattern, text)
        if m:
            groups = [g for g in m.groups() if g is not None]
            try:
                # 最后一个捕获组是数字
                h = int(groups[-1])
            except (ValueError, IndexError):
                h = int(m.group(1))
            hour = fn(h)
            break

    # "刚刚"/"现在"/"刚才" → 当前时间
    if hour is None:
        if re.search(r'(刚刚|现在|刚才|刚)', text):
            return now.isoformat()
        return None

    # 分钟
    minute = 0
    if re.search(r'(\d{1,2})\s*点\s*半', text):
        minute = 30
    else:
        m_min = re.search(r'(\d{1,2})\s*点\s*(\d{1,2})\s*分', text)
        if m_min:
            minute = int(m_min.group(2))

    hour = max(0, min(hour, 23))
    minute = max(0, min(minute, 59))

    parsed = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    # 如果解析时间在未来，回退一天
    if parsed > now:
        parsed -= timedelta(days=1)

    return parsed.isoformat()


def call_llm(messages: list, temperature: float = 0.3) -> str:
    """调用大模型（同步）"""
    with httpx.Client(timeout=30) as client:
        resp = client.post(
            f"{Config.AI_API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {Config.AI_API_KEY}"},
            json={
                "model": Config.AI_MODEL,
                "messages": messages,
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def transcribe_audio(audio_base64: str, audio_format: str = "mp3") -> str:
    """语音转文字"""
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            "https://asr.tencentcloudapi.com/",
            headers={"Authorization": f"Bearer {Config.ASR_API_KEY}"},
            json={"audio": audio_base64, "format": audio_format},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("text", "")


def _keyword_fallback(user_text: str):
    """关键词兜底解析 — 不依赖 LLM，零延迟零费用"""
    text = user_text.strip()
    if not text:
        return None

    # 尿布
    diaper_kw = ['尿布', '尿不湿', '拉了', '拉屎', '拉粑粑', '尿了', '拉臭臭', '换尿', '换了尿', '拉便便', '大便']
    if any(kw in text for kw in diaper_kw):
        dt = 'wet'
        if '干' in text or '尿' in text:
            dt = 'wet'
        if '拉' in text or '粑' in text or '臭' in text or '便' in text:
            dt = 'mixed'
        if '都有' in text or ('干' in text and '湿' in text):
            dt = 'mixed'

        parsed = {"diaper_type": dt}

        t = _parse_time(text)
        if t:
            parsed['time'] = t

        return {"record_type": "diaper", "parsed": parsed, "confidence": 0.9}

    # 喂奶
    feeding_kw = ['喂奶', '喂了', '喝了', '吃了', '母乳', '奶粉', '瓶喂', '左边', '右边', '左侧', '右侧', '亲喂', '吸奶', '哺乳']
    if any(kw in text for kw in feeding_kw):
        parsed = {}

        # side：只在明确时设置，否则让前端弹窗询问
        has_left = bool(re.search(r'左', text))
        has_right = bool(re.search(r'右', text))
        has_bottle = bool(re.search(r'瓶|奶粉', text))

        if has_left and not has_right:
            parsed['side'] = 'left'
        elif has_right and not has_left:
            parsed['side'] = 'right'
        elif has_bottle:
            parsed['side'] = 'bottle'
        # 否则不设置 side，由前端检测缺失并弹窗

        dur_match = re.search(r'(\d+)\s*(分钟|分)', text)
        vol_match = re.search(r'(\d+)\s*(ml|毫升|oz)', text)
        parsed['duration_minutes'] = int(dur_match.group(1)) if dur_match else 0
        parsed['amount_ml'] = int(vol_match.group(1)) if vol_match else 0
        if parsed['amount_ml'] == 0:
            vol_match2 = re.search(r'(\d{2,3})\s*(?!分|分钟)', text)
            if vol_match2:
                parsed['amount_ml'] = int(vol_match2.group(1))

        # 时间解析
        start_time = _parse_time(text)
        if start_time:
            parsed['start_time'] = start_time
            if parsed['duration_minutes'] > 0:
                dt = datetime.fromisoformat(start_time)
                parsed['end_time'] = (dt + timedelta(minutes=parsed['duration_minutes'])).isoformat()

        return {"record_type": "feeding", "parsed": parsed, "confidence": 0.9}

    # 睡眠
    sleep_kw = ['睡了', '睡觉', '小睡', '午睡', '打盹', 'nap']
    if any(kw in text for kw in sleep_kw):
        dur_match = re.search(r'(\d+)\s*(分钟|分|小时|h)', text)
        duration = int(dur_match.group(1)) if dur_match else 0
        if '小时' in text or 'h' in text:
            duration = duration * 60 if duration else 30
        if duration == 0:
            duration = 30  # 默认30分钟

        parsed = {"duration_minutes": duration}

        start_time = _parse_time(text)
        if start_time:
            parsed['start_time'] = start_time
            dt = datetime.fromisoformat(start_time)
            parsed['end_time'] = (dt + timedelta(minutes=duration)).isoformat()

        return {"record_type": "sleep", "parsed": parsed, "confidence": 0.85}

    return None


VOICE_PARSE_PROMPT = """你是一个育儿助手，负责将用户的语音录入解析为结构化的育儿记录。

用户说了一段话，请判断它属于哪种记录类型，并提取关键信息。

记录类型：
- "feeding"：喂奶记录 → 提取 side（left/right/bottle）、duration_minutes（时长分钟数）、amount_ml（奶量ml，无则为0）
- "sleep"：睡眠记录 → 提取 duration_minutes（时长分钟数，含"小时"则×60，无时长默认30）
- "diaper"：尿布记录 → 提取 diaper_type（wet/dry/mixed）

时间规则（极其重要）：
- 如果用户提到了具体时间（如"上午9点"、"下午3点半"、"4点"），必须提取 start_time（或尿布用 time）为 ISO 8601 格式（YYYY-MM-DDTHH:MM:SS），默认日期为今天
- 如果当前时间已过用户说的时间点，且用户未指定日期 → 日期使用今天（即记录发生时间而非当前时间）
- 例如：现在是凌晨1点，用户说"下午4点睡了半小时" → start_time 使用今天下午4点
- 如果有时长，同时计算 end_time = start_time + duration_minutes
- 没提到时间则不填 start_time/time

喂奶 side 规则：
- 用户说了左边/左侧 → side: "left"
- 用户说了右边/右侧 → side: "right"  
- 用户说了瓶喂/奶粉 → side: "bottle"
- 用户没明确说用哪边/什么方式 → **不要填 side 字段**，由前端弹窗让用户选择

请严格按以下 JSON 格式输出，不要输出其他内容：
{
  "record_type": "feeding",
  "parsed": {
    "side": "left",
    "duration_minutes": 15,
    "amount_ml": 0,
    "start_time": "2026-06-20T09:00:00",
    "end_time": "2026-06-20T09:15:00"
  },
  "confidence": 0.95
}

用户语音内容：
{user_text}"""


def parse_voice_input(user_text: str) -> dict:
    """解析语音输入，返回结构化记录（关键词优先，LLM兜底）"""
    # 先走关键词兜底（零延迟、零费用）
    fallback = _keyword_fallback(user_text)
    if fallback:
        return fallback

    messages = [
        {"role": "system", "content": "你是一个精确的语音解析器，只输出JSON。"},
        {"role": "user", "content": VOICE_PARSE_PROMPT.format(user_text=user_text)},
    ]
    try:
        result_text = call_llm(messages, temperature=0.1)
        result_text = result_text.strip()
        # 移除可能的 markdown 代码块标记
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:])
            if result_text.endswith("```"):
                result_text = result_text[:-3]
        # 尝试提取第一个 JSON 对象
        brace_start = result_text.find("{")
        brace_end = result_text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            result_text = result_text[brace_start:brace_end+1]
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"Voice parse failed: {e}, raw: {result_text[:200] if 'result_text' in dir() else 'N/A'}")
        return {"record_type": "unknown", "parsed": {}, "confidence": 0}


CHAT_SYSTEM_PROMPT = """你是一个专业的育儿顾问助手，你可以：
1. 回答育儿相关问题（喂养、睡眠、发育、护理等）
2. 基于用户提供的宝宝数据给出个性化建议
3. 安抚新手父母的焦虑情绪

要求：
- 回答专业、温暖、有同理心
- 基于 WHO 和权威儿科指南
- 如涉及医疗建议，提醒用户咨询专业医生
- 用中文回答，简洁明了"""


def chat_with_parent(user_message: str, context_data: dict = None) -> str:
    """育儿顾问对话"""
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    if context_data:
        messages.append({
            "role": "system",
            "content": f"当前宝宝数据摘要：{json.dumps(context_data, ensure_ascii=False)}",
        })
    messages.append({"role": "user", "content": user_message})
    return call_llm(messages, temperature=0.7)
