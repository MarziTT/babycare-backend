"""AI 相关 API - 语音解析、智能问答"""
from flask import Blueprint, request, jsonify
from services.ai_service import parse_voice_input, chat_with_parent, transcribe_audio

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

    if text:
        result = parse_voice_input(text)
        result["raw_text"] = text
    else:
        result = {"record_type": "unknown", "parsed": {}, "confidence": 0, "raw_text": text}

    return jsonify({"code": 0, "data": result, "message": "ok"})


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
