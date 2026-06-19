"""AI 服务封装 - LLM 调用、意图解析、语音转文字（同步版本）"""
import json
import logging
import httpx
from config import Config

logger = logging.getLogger(__name__)


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
        return {"record_type": "diaper", "parsed": {"diaper_type": dt}, "confidence": 0.9}

    # 喂奶
    feeding_kw = ['喂奶', '喂了', '喝了', '吃了', '母乳', '奶粉', '瓶喂', '左边', '右边', '左侧', '右侧', '亲喂', '吸奶', '哺乳']
    if any(kw in text for kw in feeding_kw):
        side = 'right'
        if '左' in text:
            side = 'left'
        if '瓶' in text or '奶粉' in text:
            side = 'bottle'

        import re
        dur_match = re.search(r'(\d+)\s*(分钟|分)', text)
        vol_match = re.search(r'(\d+)\s*(ml|毫升|oz)', text)
        duration = int(dur_match.group(1)) if dur_match else 0
        amount = int(vol_match.group(1)) if vol_match else 0
        if amount == 0:
            vol_match2 = re.search(r'(\d{2,3})\s*(?!分|分钟)', text)
            if vol_match2:
                amount = int(vol_match2.group(1))

        return {"record_type": "feeding", "parsed": {"side": side, "duration_minutes": duration, "amount_ml": amount}, "confidence": 0.9}

    # 睡眠
    sleep_kw = ['睡了', '睡觉', '小睡', '午睡', '打盹', 'nap']
    if any(kw in text for kw in sleep_kw):
        import re
        dur_match = re.search(r'(\d+)\s*(分钟|分|小时|h)', text)
        duration = int(dur_match.group(1)) if dur_match else 0
        if '小时' in text or 'h' in text:
            duration = duration * 60 if duration else 30
        if duration == 0:
            duration = 30  # 默认30分钟
        return {"record_type": "sleep", "parsed": {"duration_minutes": duration}, "confidence": 0.85}

    return None


VOICE_PARSE_PROMPT = """你是一个育儿助手，负责将用户的语音录入解析为结构化的育儿记录。

用户说了一段话，请判断它属于哪种记录类型，并提取关键信息。

记录类型：
- "feeding"：喂奶记录 → 提取 side（left/right/bottle）、duration_minutes（时长）、amount_ml（瓶喂奶量）
- "sleep"：睡眠记录 → 提取 duration_minutes（时长）
- "diaper"：尿布记录 → 提取 diaper_type（wet/dry/mixed）

请严格按以下 JSON 格式输出，不要输出其他内容：
{
  "record_type": "feeding",
  "parsed": {
    "side": "left",
    "duration_minutes": 15,
    "amount_ml": 0
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
