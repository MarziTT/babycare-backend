"""BabyCare 育儿助手 - 数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

class FeedType(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    BOTTLE = "bottle"

class DiaperType(str, Enum):
    WET = "wet"
    DRY = "dry"
    MIXED = "mixed"

@dataclass
class FeedingRecord:
    id: str = ""
    baby_id: str = ""
    family_id: str = ""
    feed_type: FeedType = FeedType.LEFT
    start_time: str = ""       # ISO 8601
    end_time: str = ""         # ISO 8601
    duration_minutes: int = 0
    amount_ml: int = 0         # 瓶喂时必填
    note: str = ""
    recorded_by: str = ""      # 记录人 openid
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "baby_id": self.baby_id,
            "family_id": self.family_id,
            "feed_type": self.feed_type.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration_minutes,
            "amount_ml": self.amount_ml,
            "note": self.note,
            "recorded_by": self.recorded_by,
            "created_at": self.created_at,
        }

@dataclass
class SleepRecord:
    id: str = ""
    baby_id: str = ""
    family_id: str = ""
    start_time: str = ""
    end_time: str = ""
    duration_minutes: int = 0
    note: str = ""
    recorded_by: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "baby_id": self.baby_id,
            "family_id": self.family_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_minutes": self.duration_minutes,
            "note": self.note,
            "recorded_by": self.recorded_by,
            "created_at": self.created_at,
        }

@dataclass
class DiaperRecord:
    id: str = ""
    baby_id: str = ""
    family_id: str = ""
    diaper_type: DiaperType = DiaperType.WET
    time: str = ""
    note: str = ""
    recorded_by: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "baby_id": self.baby_id,
            "family_id": self.family_id,
            "diaper_type": self.diaper_type.value,
            "time": self.time,
            "note": self.note,
            "recorded_by": self.recorded_by,
            "created_at": self.created_at,
        }

@dataclass
class AIParseResult:
    """语音录入 AI 解析结果"""
    record_type: str = ""       # feeding / sleep / diaper
    parsed: dict = field(default_factory=dict)
    confidence: float = 0.0
    raw_text: str = ""

@dataclass
class AnalysisReport:
    """AI 分析报告"""
    baby_id: str = ""
    period: str = "weekly"     # daily / weekly / monthly
    feeding_summary: dict = field(default_factory=dict)
    sleep_summary: dict = field(default_factory=dict)
    diaper_summary: dict = field(default_factory=dict)
    trends: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    generated_at: str = ""
