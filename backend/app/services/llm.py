# -*- coding: utf-8 -*-
"""大模型调用：OpenAI 兼容接口（支持 DeepSeek / 千问等）。

配置：设置页填写 ai_api_url（如 https://api.deepseek.com）、ai_model；
密钥 AI_API_KEY 只从服务器环境变量读取，绝不返回给前端、不打日志。
"""
import json

import httpx

from ..config import settings


class LlmNotConfigured(Exception):
    """大模型未配置时抛出。"""


# 可抽取的评估字段及其中文说明（供 prompt 使用）
EXTRACTABLE_FIELDS = {
    "weight_kg": "体重（公斤）", "body_fat_pct": "体脂率（%）",
    "muscle_kg": "肌肉量（公斤）", "bmi": "BMI",
    "visceral_fat": "内脏脂肪等级", "chest_cm": "胸围（厘米）",
    "waist_cm": "腰围（厘米）", "hip_cm": "臀围（厘米）",
    "arm_cm": "上臂围（厘米）", "thigh_cm": "大腿围（厘米）",
    "resting_hr": "静息心率（次/分）", "blood_pressure": "血压（如120/80）",
    "injuries": "伤病史/注意事项", "height_cm": "身高（厘米）",
    "age": "年龄",
}

SYSTEM_PROMPT = (
    "你是健身房体测数据的结构化助手。用户会输入一段包含身体数据的自由文本，"
    "请从中提取以下字段并只返回 JSON 对象，不要返回其他内容：\n"
    + "\n".join(f"- {k}：{v}" for k, v in EXTRACTABLE_FIELDS.items())
    + "\n文本中没有提到的字段不要出现在 JSON 中；数字请转为数值类型。"
)


def _base_url() -> str:
    """从设置页读取接口地址（数据库优先，环境变量兜底）。"""
    from ..database import SessionLocal
    from .. import models
    db = SessionLocal()
    try:
        row = db.query(models.Setting).filter(models.Setting.key == "ai_api_url").first()
        url = (row.value if row else "") or settings.AI_API_URL
    finally:
        db.close()
    return url.rstrip("/")


def _model() -> str:
    """从设置页读取模型名。"""
    from ..database import SessionLocal
    from .. import models
    db = SessionLocal()
    try:
        row = db.query(models.Setting).filter(models.Setting.key == "ai_model").first()
        return (row.value if row else "") or settings.AI_MODEL
    finally:
        db.close()


def extract_fields(text: str) -> dict:
    """自由文本 -> 结构化评估字段（JSON dict）。未配置时抛 LlmNotConfigured。"""
    url, model, key = _base_url(), _model(), settings.AI_API_KEY
    if not url or not key or not model:
        raise LlmNotConfigured("未配置大模型：请在设置页填写接口地址与模型，并在服务器环境变量中配置 AI_API_KEY")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=60) as client:
        resp = client.post(f"{url}/chat/completions", json=payload, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"大模型接口错误 {resp.status_code}：{resp.text[:200]}")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(f"大模型返回无法解析：{e}")
    # 只保留白名单字段，防止脏数据入库
    return {k: v for k, v in data.items() if k in EXTRACTABLE_FIELDS}
