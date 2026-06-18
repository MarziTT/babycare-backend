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
    """解析语音输入，返回结构化记录"""
    messages = [
        {"role": "system", "content": "你是一个精确的语音解析器，只输出JSON。"},
        {"role": "user", "content": VOICE_PARSE_PROMPT.format(user_text=user_text)},
    ]
    try:
        result_text = call_llm(messages, temperature=0.1)
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"Voice parse failed: {e}")
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
