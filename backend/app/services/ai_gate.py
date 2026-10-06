# -*- coding: utf-8 -*-
"""AiFeatureGate：AI 功能准入与用量门控（门店级订阅）。

产品边界：系统只管理 AI 订阅状态和调用额度，不碰健身房经营收费
（会员费/私教费/课包费等）。

- 订阅主体是门店（owner 级别），不是单个客户
- 套餐（AiPlan）配置功能开关 + 每月用量上限
- 状态 trialing/active 视为有效；expired/paused 拒绝
"""
import datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..config import settings

# AI 功能清单：key -> 中文名
AI_FEATURES = {
    "extract": "自然语言录入抽取",
    "ocr": "OCR 识别体测单",
    "voice": "语音转记录",
    "plan_diet": "生成训练/饮食建议",
    "summary": "客户总结",
}

# 功能 -> 套餐用量字段的映射
FEATURE_QUOTA_FIELD = {
    "ocr": "ocr_per_month",
    "voice": "voice_minutes_per_month",
    "extract": "llm_calls_per_month",
    "plan_diet": "llm_calls_per_month",
    "summary": "llm_calls_per_month",
}

# 预置三档套餐：价格先填占位 0，由馆主在设置页修改
DEFAULT_PLANS = [
    {"name": "免费版", "monthly_price": 0, "yearly_price": 0,
     "ocr_per_month": 0, "voice_minutes_per_month": 0, "llm_calls_per_month": 50,
     "features": {"extract": True, "ocr": False, "voice": False,
                  "plan_diet": False, "summary": False}},
    {"name": "专业版", "monthly_price": 0, "yearly_price": 0,
     "ocr_per_month": 100, "voice_minutes_per_month": 300, "llm_calls_per_month": 1000,
     "features": {"extract": True, "ocr": True, "voice": True,
                  "plan_diet": True, "summary": False}},
    {"name": "旗舰版", "monthly_price": 0, "yearly_price": 0,
     "ocr_per_month": 500, "voice_minutes_per_month": 1500, "llm_calls_per_month": 5000,
     "features": {"extract": True, "ocr": True, "voice": True,
                  "plan_diet": True, "summary": True}},
]

VALID_STATUSES = ("trialing", "active")


def _setting(db: Session, key: str, fallback: str = "") -> str:
    row = db.query(models.Setting).filter(models.Setting.key == key).first()
    return row.value if row else fallback


def ai_enabled(db: Session) -> bool:
    return _setting(db, "ai_enabled", "false").lower() == "true"


def ensure_default_plans(db: Session):
    """启动时预置三档套餐（表空时才建，不覆盖馆主修改）。"""
    if db.query(models.AiPlan).count() == 0:
        for p in DEFAULT_PLANS:
            db.add(models.AiPlan(**p))
        db.commit()


def active_store_subscription(db: Session) -> models.AiSubscription | None:
    """门店当前有效订阅（trialing/active 且未过期）。"""
    now = datetime.datetime.now()
    sub = (db.query(models.AiSubscription)
           .filter(models.AiSubscription.status.in_(VALID_STATUSES),
                   models.AiSubscription.expires_at > now)
           .order_by(models.AiSubscription.id.desc()).first())
    if sub and sub.status == "expired":
        return None
    return sub


def _month_start() -> datetime.datetime:
    now = datetime.datetime.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def month_usage(db: Session, kind: str) -> float:
    """本月某类 AI 功能的已用量（voice 按分钟累加，其余按次数）。"""
    total = (db.query(func.sum(models.AiUsage.amount))
             .filter(models.AiUsage.kind == kind,
                     models.AiUsage.created_at >= _month_start()).scalar())
    return float(total or 0)


def quota_remaining(db: Session, plan: models.AiPlan, kind: str) -> float:
    """某套餐下某类功能的本月剩余额度（0 上限视为 0 次，不可用）。"""
    field = FEATURE_QUOTA_FIELD.get(kind)
    if not field:
        return 0
    limit = getattr(plan, field, 0) or 0
    return max(0.0, float(limit) - month_usage(db, kind))


def check_ai_access(db: Session, user: models.User, feature: str):
    """AI 功能准入校验（AiFeatureGate），不通过则抛 403。

    feature 为 AI_FEATURES 的 key，如 "extract" / "ocr" / "voice"。
    """
    if feature not in AI_FEATURES:
        raise HTTPException(status_code=400, detail=f"未知 AI 功能：{feature}")
    if not ai_enabled(db):
        raise HTTPException(status_code=403, detail="AI 功能未开启，请联系馆主")
    url = _setting(db, "ai_api_url", settings.AI_API_URL)
    model = _setting(db, "ai_model", settings.AI_MODEL)
    if not url or not settings.AI_API_KEY or not model:
        raise HTTPException(status_code=403, detail="大模型未配置，请联系馆主")
    sub = active_store_subscription(db)
    if not sub or not sub.plan:
        raise HTTPException(status_code=403, detail="门店 AI 订阅未生效（试用中/有效订阅），请联系馆主")
    features = sub.plan.features or {}
    if not features.get(feature):
        raise HTTPException(
            status_code=403,
            detail=f"当前套餐（{sub.plan.name}）不含「{AI_FEATURES[feature]}」功能")
    if quota_remaining(db, sub.plan, feature) <= 0:
        raise HTTPException(
            status_code=403,
            detail=f"「{AI_FEATURES[feature]}」本月额度已用完")


def record_usage(db: Session, user_id: int, kind: str, amount: float = 1.0):
    """记录一次 AI 调用（用量统计；voice 按分钟数记 amount）。"""
    db.add(models.AiUsage(user_id=user_id, kind=kind, amount=amount))
    db.commit()


def subscription_summary(db: Session) -> dict:
    """馆主用量面板：当前订阅、套餐、各功能剩余额度。"""
    sub = active_store_subscription(db)
    if not sub or not sub.plan:
        return {"subscription": None}
    plan = sub.plan
    quotas = {}
    for feature, label in AI_FEATURES.items():
        field = FEATURE_QUOTA_FIELD[feature]
        limit = getattr(plan, field, 0) or 0
        used = month_usage(db, feature)
        quotas[feature] = {"label": label, "limit": limit, "used": used,
                           "remaining": max(0.0, float(limit) - used),
                           "enabled": bool((plan.features or {}).get(feature))}
    return {
        "subscription": {
            "id": sub.id, "plan_name": plan.name, "status": sub.status,
            "started_at": sub.started_at, "expires_at": sub.expires_at,
        },
        "quotas": quotas,
    }
