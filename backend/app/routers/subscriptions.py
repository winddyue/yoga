# -*- coding: utf-8 -*-
"""AI 订阅管理（门店级 SaaS）：套餐配置、订阅开通、用量统计。

产品边界：系统只管理 AI 订阅状态和调用额度，不碰健身房经营收费
（会员费/私教费/课包费等）。

订阅开通目前由工作人员后台手动创建（原型保留）。
TODO(未来在线收款)：此处应改为支付回调驱动——
  1. 馆主在设置页选套餐下单 -> 生成订单（需新增订单表 + 幂等键）
  2. 跳转微信支付/支付宝/Stripe 收银台
  3. 支付平台回调确认成功后，才将 AiSubscription 置为 active
  4. 账单与退款只针对 AI SaaS，不涉及健身房客户的钱
在支付接通前，不要把本接口当作线上收费依据。
"""
import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db
from ..services import ai_gate, audit as audit_service

router = APIRouter(prefix="/api/ai", tags=["AI 订阅"])


@router.get("/plans", response_model=list[schemas.AiPlanOut])
def list_plans(db: Session = Depends(get_db),
               _: models.User = Depends(auth_lib.get_current_user)):
    """AI 套餐列表（免费版/专业版/旗舰版）。"""
    ai_gate.ensure_default_plans(db)
    return db.query(models.AiPlan).order_by(models.AiPlan.id).all()


@router.put("/plans/{plan_id}", response_model=schemas.AiPlanOut)
def update_plan(plan_id: int, data: schemas.AiPlanIn,
                db: Session = Depends(get_db),
                user: models.User = Depends(auth_lib.require_owner)):
    """修改套餐配置（仅馆主）：价格、用量上限、功能开关。"""
    plan = db.query(models.AiPlan).filter(models.AiPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")
    for field in ("name", "monthly_price", "yearly_price",
                  "ocr_per_month", "voice_minutes_per_month",
                  "llm_calls_per_month", "features"):
        value = getattr(data, field)
        if value is not None:
            if field == "features":
                # 只接受已知功能 key，防止脏数据
                clean = {k: bool(v) for k, v in value.items()
                         if k in ai_gate.AI_FEATURES}
                plan.features = {**{k: False for k in ai_gate.AI_FEATURES}, **clean}
            else:
                setattr(plan, field, value)
    db.commit()
    db.refresh(plan)
    audit_service.log(db, user.id, "ai_plan.update", "ai_plan", plan.id)
    return plan


@router.get("/subscription")
def get_subscription(db: Session = Depends(get_db),
                     _: models.User = Depends(auth_lib.require_owner)):
    """门店当前 AI 订阅 + 各功能剩余额度（用量面板，仅馆主）。"""
    return ai_gate.subscription_summary(db)


@router.post("/subscriptions", response_model=schemas.AiSubscriptionOut)
def create_subscription(data: schemas.AiSubscriptionIn,
                        db: Session = Depends(get_db),
                        user: models.User = Depends(auth_lib.require_staff)):
    """为门店手动开通/续费 AI 订阅（工作人员，后台原型）。

    TODO(未来在线收款)：改为支付回调确认后激活，见本文件顶部说明。
    """
    plan = db.query(models.AiPlan).filter(models.AiPlan.id == data.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")
    if data.status not in ("trialing", "active", "paused"):
        raise HTTPException(status_code=400, detail="状态只能是 trialing / active / paused")
    now = datetime.datetime.now()
    # 有未过期的有效订阅则顺延，否则从今天起算
    existing = ai_gate.active_store_subscription(db)
    start = existing.expires_at if existing else now
    expires = start + datetime.timedelta(days=data.days)
    sub = models.AiSubscription(plan_id=plan.id, status=data.status,
                                started_at=start, expires_at=expires,
                                note=data.note or "")
    db.add(sub)
    db.commit()
    db.refresh(sub)
    audit_service.log(db, user.id, "ai_subscription.create", "ai_subscription", sub.id)
    return {"id": sub.id, "plan_id": sub.plan_id, "plan_name": plan.name,
            "status": sub.status, "started_at": sub.started_at,
            "expires_at": sub.expires_at, "note": sub.note}


@router.get("/usage")
def usage_stats(db: Session = Depends(get_db),
                _: models.User = Depends(auth_lib.require_owner)):
    """AI 用量统计（仅馆主）：按用户/类型计数。"""
    rows = (db.query(models.AiUsage.user_id, models.AiUsage.kind,
                     func.count(models.AiUsage.id).label("cnt"),
                     func.sum(models.AiUsage.amount).label("amount"),
                     models.User.username, models.User.name)
            .join(models.User, models.User.id == models.AiUsage.user_id)
            .group_by(models.AiUsage.user_id, models.AiUsage.kind,
                      models.User.username, models.User.name)
            .order_by(func.count(models.AiUsage.id).desc()).all())
    return [{"user_id": r.user_id, "username": r.username, "name": r.name,
             "kind": r.kind, "count": r.cnt,
             "amount": float(r.amount or 0)} for r in rows]
