"""AI 相关 API - 语音解析、智能问答"""
import logging
from flask import Blueprint, request, jsonify
from services.ai_service import parse_voice_input, chat_with_parent, smart_agent, transcribe_audio

logger = logging.getLogger(__name__)

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/api/ai/voice-parse", methods=["POST"])
def voice_parse():
    """解析语音输入文本为结构化记录"""
    data = request.json
    user_text = data.get("text", "")
    if not user_text:
        return jsonify({"code": 400, "message": "请提供语音识别文本"}), 400

    try:
        result = parse_voice_input(user_text)
        return jsonify({"code": 0, "data": result, "message": "ok"})
    except Exception as e:
        logger.error(f"voice_parse failed: {e}")
        return jsonify({"code": 500, "message": str(e)}), 500


@ai_bp.route("/api/ai/voice-to-record", methods=["POST"])
def voice_to_record():
    """语音 → 结构化记录（含 ASR）"""
    data = request.json
    audio_base64 = data.get("audio", "")
    if not audio_base64:
        return jsonify({"code": 400, "message": "请提供语音数据"}), 400

    try:
        text = transcribe_audio(audio_base64, data.get("format", "mp3"))
    except Exception as e:
        return jsonify({"code": 500, "message": f"语音识别失败: {str(e)}"}), 500

    type_names = {
        "feeding": "喂奶", "sleep": "睡眠", "diaper": "尿布",
        "growth": "成长", "medication": "用药", "vaccination": "疫苗", "note": "随手记",
    }

    if text:
        result = parse_voice_input(text)
        result["text"] = text  # 前端期望的字段名（兼容 raw_text）
        result["intent"] = "record" if result.get("record_type") != "unknown" else "chat"
        tn = type_names.get(result.get("record_type"), "记录")
        result["reply"] = f"已识别：{tn}记录，确认保存吗？"
    else:
        result = {
            "record_type": "unknown",
            "parsed": {},
            "confidence": 0,
            "text": text,
            "intent": "chat",
            "reply": "没听清，再说一次吧～",
        }

    return jsonify({"code": 0, "data": result, "message": "ok"})


@ai_bp.route("/api/ai/smart", methods=["POST"])
def ai_smart():
    """智能助手 — 自动判断记录/对话意图"""
    data = request.json
    user_text = data.get("text", "")
    if not user_text:
        return jsonify({"code": 400, "message": "请输入内容"}), 400

    try:
        result = smart_agent(user_text)
        return jsonify({"code": 0, "data": result, "message": "ok"})
    except Exception as e:
        logger.error(f"smart_agent failed: {e}")
        return jsonify({
            "code": 0,
            "data": {"intent": "chat", "reply": "抱歉，出了点小问题，换个说法试试吧～"},
            "message": "ok"
        })


@ai_bp.route("/api/ai/chat", methods=["POST"])
def ai_chat():
    """AI 育儿顾问对话"""
    data = request.json
    user_message = data.get("message", "")
    context_data = data.get("context")

    if not user_message:
        return jsonify({"code": 400, "message": "请输入问题"}), 400

    try:
        reply = chat_with_parent(user_message, context_data)
        return jsonify({"code": 0, "data": {"reply": reply}, "message": "ok"})
    except Exception as e:
        logger.error(f"ai_chat failed: {e}")
        return jsonify({"code": 500, "message": str(e)}), 500
