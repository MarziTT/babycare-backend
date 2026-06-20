"""AI 服务封装 - LLM 调用、意图解析、语音转文字（同步版本）"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone
import httpx
from config import Config

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))  # 中国标准时间 UTC+8

# 中文数字 → 整数映射
_CN_NUM = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'半':0.5,'两':2}
_CN_NUM_MAP = {'零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,'两':2}


def _parse_cn_duration_minutes(text: str) -> int | None:
    """解析中文时长文本，返回分钟数。支持：三十分钟/十五分钟/半小时/一小时/一个半小时 等"""
    # 阿拉伯数字优先
    m = re.search(r'(\d+(?:\.\d+)?)\s*(分钟|分|小时|h)', text)
    if m:
        val = float(m.group(1))
        unit = m.group(2)
        if unit in ('小时', 'h'):
            val *= 60
        return int(val)

    # 一个半小时 → 90
    m = re.search(r'一[个]?半\s*小时', text)
    if m:
        return 90

    # 半小时 → 30
    m = re.search(r'半[个]?\s*(小时|钟头)', text)
    if m:
        return 30
    m = re.search(r'半\s*分钟', text)
    if m:
        return 0  # 半分钟太短，返回0忽略

    # X小时Y分钟 / X小时半 / X个半小时
    m = re.search(r'([一二两三四五六七八九十])\s*[个]?\s*小时\s*([一二三四五半])?\s*[十]?\s*([一二三四五六七八九]?\s*分钟?)?', text)
    if m:
        hours = _CN_NUM_MAP.get(m.group(1), 0)
        total = hours * 60
        sub = m.group(2) if m.group(2) else ''
        if sub == '半':
            total += 30
        elif sub in _CN_NUM_MAP:
            total += _CN_NUM_MAP[sub] * 10 if m.group(3) else _CN_NUM_MAP[sub]
        if m.group(3):
            total += _CN_NUM_MAP.get(m.group(3).rstrip('分钟'), 0)
        return total

    # X十分钟
    m = re.search(r'([一二两三四五六七八九])?十([一二三四五六七八九])?\s*分钟', text)
    if m:
        tens = _CN_NUM_MAP.get(m.group(1), 1) if m.group(1) else 1
        ones = _CN_NUM_MAP.get(m.group(2), 0) if m.group(2) else 0
        return tens * 10 + ones

    # 纯数字 X分钟（如"八分钟"、"五分钟"）
    m = re.search(r'([一二两三四五六七八九])\s*分钟', text)
    if m:
        return _CN_NUM_MAP.get(m.group(1), 0)

    # X个小时
    m = re.search(r'([一二两三四五六七八九十])\s*[个]?\s*小时', text)
    if m:
        return _CN_NUM_MAP.get(m.group(1), 0) * 60

    # 十X分钟（十前面无数字）
    m = re.search(r'十\s*([一二三四五六七八九])?\s*分钟', text)
    if m:
        return 10 + (_CN_NUM_MAP.get(m.group(1), 0) if m.group(1) else 0)

    return None


def _parse_time(text: str) -> str | None:
    """从文本中提取时间点，返回 ISO 字符串（北京时间 UTC+8）。
    
    支持：上午9点、下午4点、晚上8点、凌晨3点、6点半、8点20分、刚刚/现在
    智能回退：如果解析时间在未来（如凌晨说"下午4点"），自动回退一天。
    """
    now = datetime.now(CST)

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
    feeding_kw = ['喂奶', '喝奶', '吃奶', '喂了', '喝了', '吃了', '母乳', '奶粉', '瓶喂',
                  '左边', '右边', '左侧', '右侧', '亲喂', '吸奶', '哺乳', '吃完了', '喝完了',
                  '泡奶粉', '冲奶粉', '冲奶', '泡奶', '喂完了', '喝饱了', '吃饱了',
                  '饿了', '饿', '想吃', '想喝', '要喝', '要吃', '饿哭', '饿醒',
                  '奶瓶', '吸出来', '挤奶', '存储奶', '冻奶', '温奶', '热奶']
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

        cn_dur = _parse_cn_duration_minutes(text)
        parsed['duration_minutes'] = cn_dur if cn_dur is not None else 0
        vol_match = re.search(r'(\d+)\s*(ml|毫升|oz)', text)
        parsed['amount_ml'] = int(vol_match.group(1)) if vol_match else 0
        if parsed['amount_ml'] == 0:
            vol_match2 = re.search(r'(\d{2,3})\s*(?!分|分钟)', text)
            if vol_match2:
                parsed['amount_ml'] = int(vol_match2.group(1))

        # 时间解析
        start_time = _parse_time(text)
        if start_time:
            dt = datetime.fromisoformat(start_time)
            # "刚刚/刚/现在" + 有持续时长 → 行为刚结束，now 是 end_time
            if parsed['duration_minutes'] > 0 and re.search(r'(刚刚|现在|刚才|刚)', text):
                parsed['end_time'] = dt.isoformat()
                parsed['start_time'] = (dt - timedelta(minutes=parsed['duration_minutes'])).isoformat()
            else:
                parsed['start_time'] = start_time
                if parsed['duration_minutes'] > 0:
                    parsed['end_time'] = (dt + timedelta(minutes=parsed['duration_minutes'])).isoformat()

        return {"record_type": "feeding", "parsed": parsed, "confidence": 0.9}

    # ========== 睡眠 ==========
    sleep_kw = ['睡了', '睡觉', '小睡', '午睡', '打盹', 'nap', '睡着', '睡着了', '刚睡醒',
                 '睡醒', '醒了', '眯了', '眯一会', '眯一下', '睡了一觉', '小憩', '瞌睡',
                 '困了', '困', '想睡', '哄睡', '陪睡', '入睡', '深睡', '浅睡']
    if any(kw in text for kw in sleep_kw):
        duration = _parse_cn_duration_minutes(text)
        if duration is None:
            duration = 0

        parsed = {}
        if duration > 0:
            parsed['duration_minutes'] = duration

        start_time = _parse_time(text)
        if start_time:
            # "刚刚/刚/现在" + 有持续时长 → 睡眠刚结束，now 是 end_time
            dt = datetime.fromisoformat(start_time)
            if duration > 0 and re.search(r'(刚刚|现在|刚才|刚)', text):
                parsed['end_time'] = dt.isoformat()
                parsed['start_time'] = (dt - timedelta(minutes=duration)).isoformat()
            else:
                parsed['start_time'] = start_time
                if duration > 0:
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

        med_name = None
        for kw in med_kw[:4] + med_kw[7:]:
            if kw in text:
                med_name = kw
                break

        # 提取体温
        temp_match = re.search(r'体温\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(度|℃)?', text)
        temp_match2 = re.search(r'(\d{2,3}(?:\.\d+)?)\s*(度|℃)', text)
        temp_raw = temp_match or temp_match2
        dosage = ''
        if temp_raw:
            dosage = temp_raw.group(1)
            unit = '℃'
        else:
            unit = ''

        # 提取剂量
        dose_match = re.search(r'(\d+(?:\.\d+)?)\s*(ml|毫升|mg|毫克|滴)', text)
        if dose_match and not temp_raw:
            dosage = dose_match.group(1)
            unit = dose_match.group(2)

        parsed['medicine_name'] = med_name or text[:20]
        if dosage:
            parsed['dosage'] = dosage
            parsed['unit'] = unit

        t = _parse_time(text)
        parsed['start_time'] = t or datetime.now().isoformat()

        return {"record_type": "medication", "parsed": parsed, "confidence": 0.75}

    # ========== 疫苗接种 ==========
    vacc_kw = ['疫苗', '打针', '接种', '乙肝', '卡介苗', '脊灰', '百白破', '麻腮风', '水痘', '肺炎', '轮状', '流脑']
    if any(kw in text for kw in vacc_kw):
        parsed = {}
        for kw in vacc_kw[3:]:
            if kw in text:
                parsed['vaccine_name'] = kw
                break
        if not parsed.get('vaccine_name'):
            parsed['vaccine_name'] = text[:20]

        t = _parse_time(text)
        parsed['scheduled_date'] = (t or datetime.now().isoformat())[:10]
        parsed['status'] = 'completed'

        return {"record_type": "vaccination", "parsed": parsed, "confidence": 0.8}

    return None


VOICE_PARSE_PROMPT = """你是一个精准的语音解析器，从育儿记录语音中提取结构化信息。

输入：用户说的一句育儿记录（如"左边喂了15分钟"、"宝宝睡了半小时"）

你的任务是提取记录类型和关键字段。必须返回合法 JSON，不要输出其他内容。

记录类型与字段映射：
- "feeding"：喂奶记录 → 提取 side（left/right/bottle）、duration_minutes（时长分钟数）、amount_ml（奶量ml，无则为0）
- "sleep"：睡眠记录 → 提取 duration_minutes（时长分钟数，含"小时"则×60，无时长不填）
- "diaper"：尿布记录 → 提取 diaper_type（wet/dry/mixed）
- "growth"：成长记录 → 提取 height_cm（身高cm）、weight_kg（体重kg）、head_circumference_cm（头围cm）
- "medication"：用药记录 → 提取 medicine_name、dosage、unit
- "vaccination"：疫苗接种 → 提取 vaccine_name、scheduled_date
- "note"：随手记/无法归类 → 提取 text、time

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


SMART_AGENT_PROMPT = """你是一个智能育儿助手，集成了记录解析和育儿问答功能。

根据用户输入，判断意图并返回相应结果：

【意图判断】
1. 如果用户在记录宝宝行为（喂奶、睡眠、尿布、成长数据、用药、疫苗等）→ intent: "record"
2. 如果是育儿咨询、闲聊、问候 → intent: "chat"

【记录解析规则（intent=record）】
提取结构化字段，规则与 voice-parse 一致：

record_type 判断：
- "feeding"：喂奶相关 → side(left/right/bottle，不确定则不填)、duration_minutes、amount_ml(无则为0)、start_time、end_time
- "sleep"：睡眠相关 → duration_minutes(小时×60，无则不填)、start_time、end_time
- "diaper"：尿布相关 → diaper_type(wet/dry/mixed)、time
- "growth"：成长数据 → height_cm、weight_kg、head_circumference_cm、record_date
- "medication"：用药/生病 → medicine_name、dosage、unit、start_time
- "vaccination"：疫苗接种 → vaccine_name、scheduled_date、status
- "note"：其他无法明确归类 → text、time

时间规则：
- 提及具体时间（"上午9点"、"下午3点半"）→ start_time/time 为今天该时刻，ISO 8601
- 没提时间 → 不填
- 有时长 → 计算 end_time = start_time + duration_minutes

reply 字段：始终生成一句友好的确认对话，让用户知道解析结果。例如：
- "已识别：左侧喂奶 15 分钟，确认保存吗？"
- "已识别：宝宝睡了 30 分钟，要保存这条睡眠记录吗？"

【对话回复规则（intent=chat）】
- 专业、温暖、简洁
- 育儿相关：基于 WHO 和权威儿科指南
- 涉及医疗建议时提醒咨询医生
- 非育儿闲聊：友好简短回应

【输出格式】
严格返回 JSON，不要其他内容：
{"intent": "record", "record_type": "feeding", "parsed": {"side": "left", "duration_minutes": 15, "amount_ml": 0, "start_time": "2026-06-20T09:00:00"}, "confidence": 0.95, "reply": "已识别：左侧喂奶 15 分钟，确认保存吗？"}
或
{"intent": "chat", "reply": "宝宝现在多大了？这个阶段的宝宝..."}

用户输入：
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


def smart_agent(user_text: str) -> dict:
    """智能助手 - 意图识别 + 记录解析 + 对话回复（关键词优先，LLM兜底）"""
    # 先走关键词兜底判断是否有记录意图
    fallback = _keyword_fallback(user_text)
    if fallback:
        # 有记录意图，生成友好的 reply
        type_names = {
            "feeding": "喂奶",
            "sleep": "睡眠",
            "diaper": "尿布",
            "growth": "成长",
            "medication": "用药",
            "vaccination": "疫苗",
            "note": "随手记",
        }
        tn = type_names.get(fallback["record_type"], "记录")
        reply = f"已识别：{tn}记录，确认保存吗？"
        fallback["reply"] = reply
        fallback["intent"] = "record"
        return fallback

    # LLM 判断意图
    messages = [
        {"role": "system", "content": "你是一个智能育儿助手，精确返回JSON。"},
        {"role": "user", "content": SMART_AGENT_PROMPT.format(user_text=user_text)},
    ]
    try:
        result_text = call_llm(messages, temperature=0.1)
        result_text = result_text.strip()
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            result_text = "\n".join(lines[1:])
            if result_text.endswith("```"):
                result_text = result_text[:-3]
        brace_start = result_text.find("{")
        brace_end = result_text.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            result_text = result_text[brace_start:brace_end+1]
        return json.loads(result_text)
    except Exception as e:
        logger.error(f"Smart agent failed: {e}")
        return {"intent": "chat", "reply": "抱歉，我暂时没理解您的意思，可以换个说法试试？"}


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
