# OCR / ASR / 大模型对接文档

三路录入统一流程：**采集 → 转文字/抽字段 → 人工确认 → 入库**。
敏感信息入库前统一走同意校验（`require_sensitive_consent`）。

## 1. 拍照 OCR（体测单识别）

- 前端：评估页上传体测单照片 → `POST /api/ocr/parse`（multipart `file`）。
- 后端：`app/routers/ocr.py` 转发图片到 `OCR_API_URL`，返回识别出的字段。
- 配置：设置页填写接口地址；密钥放服务器环境变量 `OCR_API_KEY`。
- 对接要点：不同体测设备版式差异大，解析结果只做**预填**，必须人工确认后再保存。
- 供应商建议：阿里云/腾讯云/百度 OCR（读光/通用表格识别），按量付费。

## 2. 语音 ASR（语音转文字）

- 前端：智能录入页「语音上传」→ `POST /api/intake/voice`（multipart `file`，audio/*）。
- 后端：`app/routers/intake.py::voice_intake` 转发音频到 `ASR_API_URL`，
  返回 `{"text": "..."}`，随后自动进入第 3 步的字段抽取。
- 配置：设置页填写接口地址；密钥放环境变量 `ASR_API_KEY`；供应商可替换。
- 期望的供应商响应格式：`{"text": "识别出的文字"}`；若供应商返回格式不同，
  在 `voice_intake` 中做一次适配（集中改一处即可）。
- 供应商建议：阿里云/腾讯云实时语音识别、讯飞开放平台。

## 3. 聊天框大模型抽字段

- 接口：`POST /api/intake/extract` `{text}` → `{fields}`（候选字段+人工确认）；
  `POST /api/intake/confirm` `{client_id, fields}` 确认入库（写评估记录）。
- 实现：`app/services/llm.py`，OpenAI 兼容的 `/chat/completions` 调用，
  支持 DeepSeek（`https://api.deepseek.com`）、通义千问（OpenAI 兼容模式）。
- 配置：设置页填写 `AI 接口地址` + `模型名`（如 `deepseek-chat`），
  密钥放环境变量 `AI_API_KEY`；总开关 `ai_enabled`。
- 提示词：`llm.py::extract_fields` 内置中文提示词，要求模型**只返回 JSON**，
  字段限白名单（体重/体脂/围度/血压/伤病史等），未知字段丢弃。
- 准入：门店级 AI 订阅（`AiFeatureGate`）：门店需有试用中/有效的 AI 套餐订阅，
  且套餐包含该功能、本月额度未用完；每次调用计入 `ai_usage`（用量统计在设置页查看）。

## 密钥管理铁律

所有 Key 只放**服务端环境变量**，不进代码、不进前端、不进日志。
前端设置页仅显示「已配置/未配置」状态。
