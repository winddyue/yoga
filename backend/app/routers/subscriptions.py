# -*- coding: utf-8 -*-
"""AI 订阅：馆主定价（月/年），工作人员为客户开通，客户查看自己的订阅；
用量统计供馆主查看。"""
import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db
from ..services import ai_gate, audit as audit_service
from ..routers import settings as settings_router

router = APIRouter(prefix="/api/subscriptions", tags=["AI 订阅"])

PLAN_DAYS = {"monthly": 30, "yearly": 365}


@router.get("/pricing", response_model=schemas.PricingOut)
def get_pricing(db: Session = Depends(get_db),
                user: models.User = Depends(auth_lib.get_current_user)):
    """AI 订阅定价（所有登录用户可见）。"""
    return settings_router.ai_pricing(db)


@router.post("", response_model=schemas.SubscriptionOut)
def create_subscription(data: schemas.SubscriptionIn,
                        db: Session = Depends(get_db),
                        user: models.User = Depends(auth_lib.require_staff)):
    """为客户开通/续费 AI 订阅（工作人员）。"""
    if data.plan not in PLAN_DAYS:
        raise HTTPException(status_code=400, detail="套餐只能是 monthly / yearly")
    client = auth_lib.client_visible_to(db, user, data.client_id)
    now = datetime.datetime.now(datetime.timezone.utc)
    days = PLAN_DAYS[data.plan]
    # 有未过期的订阅则顺延，否则从今天起算
    existing = ai_gate.active_subscription(db, client.id)
    start = existing.expires_at if existing else now
    expires = start + datetime.timedelta(days=days)
    sub = models.Subscription(client_id=client.id, plan=data.plan,
                              started_at=start, expires_at=expires, status="active")
    db.add(sub)
    db.commit()
    db.refresh(sub)
    audit_service.log(db, user.id, "subscription.create", "subscription", sub.id)
    return {"id": sub.id, "client_id": sub.client_id, "plan": sub.plan,
            "started_at": sub.started_at, "expires_at": sub.expires_at,
            "status": sub.status}


@router.get("/mine", response_model=schemas.SubscriptionOut | None)
def my_subscription(db: Session = Depends(get_db),
                    user: models.User = Depends(auth_lib.get_current_user)):
    """客户查看自己的 AI 订阅状态。"""
    client = auth_lib.get_own_client(db, user)
    sub = ai_gate.active_subscription(db, client.id)
    if not sub:
        return None
    return {"id": sub.id, "client_id": sub.client_id, "plan": sub.plan,
            "started_at": sub.started_at, "expires_at": sub.expires_at,
            "status": sub.status}


@router.get("/usage")
def usage_stats(db: Session = Depends(get_db),
                _: models.User = Depends(auth_lib.require_owner)):
    """AI 用量统计（仅馆主）：按用户/类型计数。"""
    rows = (db.query(models.AiUsage.user_id, models.AiUsage.kind,
                     func.count(models.AiUsage.id).label("cnt"),
                     models.User.username, models.User.name)
            .join(models.User, models.User.id == models.AiUsage.user_id)
            .group_by(models.AiUsage.user_id, models.AiUsage.kind,
                      models.User.username, models.User.name)
            .order_by(func.count(models.AiUsage.id).desc()).all())
    return [{"user_id": r.user_id, "username": r.username, "name": r.name,
             "kind": r.kind, "count": r.cnt} for r in rows]
