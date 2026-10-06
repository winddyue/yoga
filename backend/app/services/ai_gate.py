# -*- coding: utf-8 -*-
"""AI 功能准入：总开关 + 大模型配置 + 客户需有效订阅。

工作人员（馆主/教练）免费使用；客户角色使用 AI 功能需购买订阅。
"""
import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..config import settings


def _setting(db: Session, key: str, fallback: str = "") -> str:
    row = db.query(models.Setting).filter(models.Setting.key == key).first()
    return row.value if row else fallback


def ai_enabled(db: Session) -> bool:
    return _setting(db, "ai_enabled", "false").lower() == "true"


def active_subscription(db: Session, client_id: int) -> models.Subscription | None:
    """客户的有效订阅（未过期）。"""
    now = datetime.datetime.now(datetime.timezone.utc)
    return (db.query(models.Subscription)
            .filter(models.Subscription.client_id == client_id,
                    models.Subscription.status == "active",
                    models.Subscription.expires_at > now).first())


def check_ai_access(db: Session, user: models.User):
    """AI 功能准入校验，不通过则抛 403。"""
    if not ai_enabled(db):
        raise HTTPException(status_code=403, detail="AI 功能未开启，请联系馆主")
    url = _setting(db, "ai_api_url", settings.AI_API_URL)
    model = _setting(db, "ai_model", settings.AI_MODEL)
    if not url or not settings.AI_API_KEY or not model:
        raise HTTPException(status_code=403, detail="大模型未配置，请联系馆主")
    if user.role == "client":
        if not user.client_id or not active_subscription(db, user.client_id):
            raise HTTPException(status_code=403, detail="AI 为付费功能，请先订阅")


def record_usage(db: Session, user_id: int, kind: str):
    """记录一次 AI 调用（用量统计）。"""
    db.add(models.AiUsage(user_id=user_id, kind=kind))
    db.commit()
