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

    # ========== 尿布 ==========
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

    # ========== 喂奶 ==========
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

    # ========== 睡眠 ==========
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

    # ========== 成长记录 ==========
    growth_kw = ['身高', '体重', '称体重', '称了', '头围', '长高', '量了身高', '量身高', '量了体重', '量体重', '量头围', '儿保']
    if any(kw in text for kw in growth_kw):
        parsed = {}

        # 身高
        h_match = re.search(r'身高\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(厘米|cm)?', text)
        h_match2 = re.search(r'(\d+(?:\.\d+)?)\s*(厘米|cm)\s*(身高|高)', text)
        if h_match:
            parsed['height_cm'] = float(h_match.group(1))
        elif h_match2:
            parsed['height_cm'] = float(h_match2.group(1))

        # 体重（斤需 ÷2）
        w_match = re.search(r'体重\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(公斤|kg|斤|克|g)?', text)
        w_match2 = re.search(r'称了\s*(\d+(?:\.\d+)?)\s*(公斤|kg|斤|克|g)?', text)
        w_raw = w_match or w_match2
        if w_raw:
            w_val = float(w_raw.group(1))
            w_unit = w_raw.group(2) or ''
            if w_unit in ('斤',):
                w_val = round(w_val / 2, 2)
            elif w_unit in ('克', 'g'):
                w_val = round(w_val / 1000, 2)
            parsed['weight_kg'] = w_val

        # 头围
        hc_match = re.search(r'头围\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(厘米|cm)?', text)
        if hc_match:
            parsed['head_circumference_cm'] = float(hc_match.group(1))

        # 时间
        t = _parse_time(text)
        if t:
            parsed['record_date'] = t[:10]
        else:
            parsed['record_date'] = datetime.now().strftime('%Y-%m-%d')

        # 只要提取到了数值就返回
        if parsed.get('height_cm') or parsed.get('weight_kg') or parsed.get('head_circumference_cm'):
            return {"record_type": "growth", "parsed": parsed, "confidence": 0.85}

        # 只说了"称了"等无具体数值 → 归为 note
        return {
            "record_type": "note",
            "parsed": {"text": text, "time": (_parse_time(text) or datetime.now().isoformat())},
            "confidence": 0.6
        }

    # ========== 用药记录 ==========
    med_kw = ['吃药', '用药', '喂药', '维生素', '维D', 'D3', 'DHA', '益生菌', '退烧药', '退烧', '体温',
              '发烧', '发热', '感冒', '咳嗽', '流鼻涕', '拉肚子', '腹泻', '便秘', '过敏', '湿疹',
              '红屁股', '吐了', '吐奶', '痱子', '补钙', '补锌', '补铁', '钙片', '锌',
              '美林', '布洛芬', '泰诺', '对乙酰', '止咳', '蒙脱石', '妈咪爱']
    if any(kw in text for kw in med_kw):
        parsed = {}

        # 药名：从关键词列表映射
        drug_map = [
            ('维生素D|维D', '维生素D'),
            ('D3(?!HA)', '维生素D3'),
            ('DHA', 'DHA'),
            ('益生菌|妈咪爱', '益生菌'),
            ('钙片|补钙|钙', '钙'),
            ('锌|补锌', '锌'),
            ('铁|补铁', '铁剂'),
            ('退烧药|美林|布洛芬', '布洛芬'),
            ('泰诺|对乙酰', '对乙酰氨基酚'),
            ('止咳', '止咳药'),
            ('蒙脱石', '蒙脱石散'),
            ('痱子', '痱子护理'),
        ]
        for pat, name in drug_map:
            if re.search(pat, text):
                parsed['medicine_name'] = name
                break

        # 没匹配到具体药名 → 症状兜底
        if not parsed.get('medicine_name'):
            symptom_map = [
                ('发烧|发热', '发烧'),
                ('咳嗽', '咳嗽'),
                ('流鼻涕', '流鼻涕'),
                ('感冒', '感冒'),
                ('拉肚子|腹泻', '腹泻'),
                ('便秘', '便秘'),
                ('过敏', '过敏'),
                ('湿疹', '湿疹'),
                ('红屁股', '红屁股'),
                ('吐了|吐奶', '呕吐'),
            ]
            for pat, sym in symptom_map:
                if re.search(pat, text):
                    parsed['medicine_name'] = sym
                    break

        if not parsed.get('medicine_name'):
            parsed['medicine_name'] = '用药记录'

        # 体温
        temp_match = re.search(r'(体温|发烧|发热)\s*[:：]?\s*(\d{2}(?:\.\d)?)\s*度?', text)
        temp_match2 = re.search(r'(\d{2}(?:\.\d)?)\s*度', text)
        t_raw = temp_match or temp_match2
        if t_raw:
            val = float(t_raw.group(2) if temp_match else t_raw.group(1))
            if 30 <= val <= 45:  # 合理体温范围
                parsed['dosage'] = str(val)
                parsed['unit'] = '度'

        # 时间
        start_time = _parse_time(text) or datetime.now().isoformat()
        parsed['start_time'] = start_time

        return {"record_type": "medication", "parsed": parsed, "confidence": 0.85}

    # ========== 疫苗接种 ==========
    vax_kw = ['疫苗', '打疫苗', '接种', '预防针', '疫苗反应']
    if any(kw in text for kw in vax_kw):
        parsed = {}

        # 提取疫苗名：常见疫苗关键词
        vax_names = {
            '乙肝': '乙肝疫苗', '卡介': '卡介苗', '脊灰': '脊髓灰质炎疫苗',
            '百白破': '百白破疫苗', '麻腮风': '麻腮风疫苗', '流脑': '流脑疫苗',
            '乙脑': '乙脑疫苗', '甲肝': '甲肝疫苗', '水痘': '水痘疫苗',
            '肺炎': '肺炎疫苗', '轮状': '轮状病毒疫苗', '手足口': '手足口病疫苗',
            '流感': '流感疫苗', 'hib': 'Hib疫苗', 'HIB': 'Hib疫苗',
            '五联': '五联疫苗', '四联': '四联疫苗', '三联': '三联疫苗',
            '13价': '13价肺炎疫苗', '23价': '23价肺炎疫苗',
        }
        for key, name in vax_names.items():
            if key in text:
                parsed['vaccine_name'] = name
                break

        if not parsed.get('vaccine_name'):
            parsed['vaccine_name'] = '疫苗接种'

        parsed['scheduled_date'] = datetime.now().strftime('%Y-%m-%d')
        parsed['status'] = 'completed'

        return {"record_type": "vaccination", "parsed": parsed, "confidence": 0.85}

    # ========== 兜底：随手记 ==========
    # 所有未能归类的输入都存为 note
    return {
        "record_type": "note",
        "parsed": {"text": text, "time": (_parse_time(text) or datetime.now().isoformat())},
        "confidence": 0.5
    }


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
