"""BabyCare 育儿助手 - 配置"""
import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "babycare-dev-secret-change-in-prod")
    DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
    PORT = int(os.environ.get("PORT", 5000))

    # 微信云开发
    WX_CLOUD_ENV = os.environ.get("WX_CLOUD_ENV", "babycare-xxx")
    WX_APPID = os.environ.get("WX_APPID", "")
    WX_SECRET = os.environ.get("WX_SECRET", "")

    # AI 服务（混元 / DeepSeek）
    AI_API_KEY = os.environ.get("AI_API_KEY") or "sk-iQ95N7rriRYBYBBrnCDwDCL0VHTzwb4IixblKROuRGaI31VW"
    AI_API_BASE = os.environ.get("AI_API_BASE") or "https://api.deepseek.com/v1"
    AI_MODEL = os.environ.get("AI_MODEL") or "deepseek-chat"

    # ASR 语音识别
    ASR_API_KEY = os.environ.get("ASR_API_KEY") or "tencent-asr-demo"
    ASR_PROVIDER = os.environ.get("ASR_PROVIDER") or "tencent"  # tencent / iflytek

    # 缓存
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # 请求限制
    RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "60"))  # 每分钟
