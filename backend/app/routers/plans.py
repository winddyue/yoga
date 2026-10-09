# -*- coding: utf-8 -*-
"""训练计划路由：自动生成、手动调整（增删改）、归档、求助。

模板生成免费开放：客户可为自己一键生成模板计划（走原模板逻辑），
工作人员不变；生成成功后通知客户。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from datetime import date, timedelta

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db
from ..services import notify as notify_service
from ..services.training import generate_plan

router = APIRouter(prefix="/api", tags=["训练计划"])


def _default_week_start() -> str:
    """本周一的 ISO 日期。

    小程序端（pages/training、pages/plans）调用生成接口时不传 week_start，
    会产出标题为「第  周计划」的空标题卡片。在这里兜底，任何调用方都能拿到
    可读的标题，不必依赖前端逐个补参数。
    """
    today = date.today()
    return (today - timedelta(days=today.weekday())).isoformat()


@router.post("/clients/{client_id}/plans/generate", response_model=schemas.TrainingPlanOut)
def generate(client_id: int, week_start: str = "",
             db: Session = Depends(get_db),
             user: models.User = Depends(auth_lib.get_current_user)):
    """按客户目标自动生成一周训练计划（旧计划自动归档）。

    模板生成免费：客户只能给自己生成，工作人员可为名下/全馆客户生成。
    """
    client = auth_lib.client_visible_to(db, user, client_id)
    if not week_start:
        week_start = _default_week_start()
    db.query(models.TrainingPlan).filter(
        models.TrainingPlan.client_id == client.id,
        models.TrainingPlan.status == "active").update({"status": "archived"})
    plan = models.TrainingPlan(client_id=client.id, week_start=week_start,
                               days=generate_plan(client.goal), created_by=user.id)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    notify_service.notify_client(
        db, client.id, "plan_new",
        "新的训练计划已生成",
        f"{client.name}，你的新一周训练计划已生成，可以开始打卡了",
        ref_type="plan", ref_id=plan.id)
    return plan


@router.post("/plan-requests")
def request_plan(data: schemas.PlanRequestIn,
                 db: Session = Depends(get_db),
                 user: models.User = Depends(auth_lib.get_current_user)):
    """客户求助：请求教练制定训练/饮食计划。通知其所属教练，无教练则 400。"""
    if data.kind not in ("training", "diet"):
        raise HTTPException(status_code=400, detail="kind 只能是 training 或 diet")
    client = auth_lib.get_own_client(db, user)  # 仅客户账号可求助
    if not client.coach_id:
        raise HTTPException(status_code=400, detail="暂未分配教练，请联系馆主")
    kind_name = "训练计划" if data.kind == "training" else "饮食方案"
    body = f"{client.name} 请求制定{kind_name}"
    if data.message:
        body += f"：{data.message}"
    notify_service.notify_coach(
        db, client.id, "plan_request",
        f"{client.name}请求制定{kind_name}", body,
        ref_type="client", ref_id=client.id)
    return {"ok": True}


@router.get("/clients/{client_id}/plans", response_model=list[schemas.TrainingPlanOut])
def list_plans(client_id: int,
               db: Session = Depends(get_db),
               user: models.User = Depends(auth_lib.get_current_user)):
    """客户的训练计划列表（含已归档）。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    return (db.query(models.TrainingPlan)
            .filter(models.TrainingPlan.client_id == client.id)
            .order_by(models.TrainingPlan.id.desc()).all())


@router.put("/plans/{plan_id}", response_model=schemas.TrainingPlanOut)
def update_plan(plan_id: int, data: schemas.TrainingPlanIn,
                db: Session = Depends(get_db),
                user: models.User = Depends(auth_lib.require_staff)):
    """手动调整训练计划：增删训练日、改时间、换动作，全量覆盖 days。仅工作人员可写。"""
    plan = db.query(models.TrainingPlan).filter(models.TrainingPlan.id == plan_id).first()
    if not plan:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="计划不存在")
    auth_lib.client_visible_to(db, user, plan.client_id)
    plan.week_start = data.week_start or plan.week_start
    plan.days = [d.model_dump() for d in data.days]
    db.commit()
    db.refresh(plan)
    return plan
