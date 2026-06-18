---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: fe7e0515290b04070c7aa137e3bf58e6_8855432a6afd11f1aa625254006c9bbf
    ReservedCode1: 6eNULI053F9zCpejDcCH/uFYjn8stgRvw2mEYvCy/cKUdKMNtToh29ofmA4Ntjq4ceu4uj6sYX5bd2kWU8sdINggPqMu0MatQoqfrkcO+ugHt7U6T5MBoTo5AqhwBE8NsLUrVJ5YWcEbrc37gM8FYSiISN52RqtEsS3gElHF1j+xfnggHhhBKrvlu2s=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: fe7e0515290b04070c7aa137e3bf58e6_8855432a6afd11f1aa625254006c9bbf
    ReservedCode2: 6eNULI053F9zCpejDcCH/uFYjn8stgRvw2mEYvCy/cKUdKMNtToh29ofmA4Ntjq4ceu4uj6sYX5bd2kWU8sdINggPqMu0MatQoqfrkcO+ugHt7U6T5MBoTo5AqhwBE8NsLUrVJ5YWcEbrc37gM8FYSiISN52RqtEsS3gElHF1j+xfnggHhhBKrvlu2s=
---

# BabyCare 育儿助手

夫妻双人协同的育儿记录微信小程序，AI 驱动的语音录入 + 智能分析。

## 架构

```
微信小程序 → 微信云开发(数据库) → Flask 后端 → DeepSeek AI
                                      ↕
                              小程序语音识别(微信免费)
```

## 项目结构

```
backend/          # Python Flask 后端
  app.py          # 主入口
  config.py       # 配置管理（从 .env 读取）
  routes/         # API 路由
    feeding.py    # 喂养记录 CRUD
    sleep.py      # 睡眠记录 CRUD
    diaper.py     # 尿布记录 CRUD
    ai.py         # AI 语音解析、育儿对话
    analysis.py   # 数据分析报告
  services/       # 业务逻辑
    ai_service.py       # DeepSeek LLM 调用、意图解析
    analysis_service.py # AI 趋势分析
  models/         # 数据模型
  prompts/        # Prompt 模板

miniapp/          # 微信小程序（原生 + TypeScript）
  pages/
    index/        # 首页概览
    feeding/add/  # 添加喂奶（含计时器）
    voice/        # 语音录入
    ai/           # AI 育儿顾问对话
    report/       # AI 分析报告
  utils/
    api.ts        # API 请求封装
    types.ts      # TypeScript 类型定义
```

## 快速开始

### 1. 后端

```bash
cd backend
cp .env.example .env        # 填写 API Key 等配置
pip install -r requirements.txt
python app.py               # 本地开发 http://localhost:5000
```

### 2. 小程序

用微信开发者工具打开 `miniapp/` 目录，修改 `utils/api.ts` 中的 `BASE_URL` 为后端地址。

### 3. 部署（Render 免费）

1. 推送 backend 到 GitHub
2. 在 [render.com](https://render.com) 创建 Web Service 连接仓库
3. 在控制台设置环境变量
4. 部署完成获得域名，更新小程序 `api.ts`

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | 微信原生小程序 + TypeScript |
| 后端 | Python Flask + gunicorn |
| AI | DeepSeek API（LLM 对话 + 意图解析） |
| 语音 | 微信 WechatSI 插件（免费） |
| 数据库 | 微信云开发 |
| 部署 | Render 免费层 |

## 环境变量

| 变量 | 必需 | 说明 |
|---|---|---|
| `AI_API_KEY` | ✅ | DeepSeek API Key |
| `AI_API_BASE` | ✅ | API 地址 |
| `AI_MODEL` | ✅ | 模型名 |
| `WX_APPID` | ✅ | 小程序 AppID |
| `WX_SECRET` | ✅ | 小程序密钥 |
| `WX_CLOUD_ENV` | ✅ | 云开发环境 ID |
| `SECRET_KEY` | ✅ | Flask 密钥 |
| `DEBUG` | - | 调试模式 |
| `PORT` | - | 端口 |
*（内容由AI生成，仅供参考）*
