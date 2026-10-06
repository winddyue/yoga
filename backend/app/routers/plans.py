# -*- coding: utf-8 -*-
"""训练计划路由：自动生成、手动调整（增删改）、归档。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db
from ..services.training import generate_plan

router = APIRouter(prefix="/api", tags=["训练计划"])


@router.post("/clients/{client_id}/plans/generate", response_model=schemas.TrainingPlanOut)
def generate(client_id: int, week_start: str = "",
             db: Session = Depends(get_db),
             user: models.User = Depends(auth_lib.get_current_user)):
    """按客户目标自动生成一周训练计划（旧计划自动归档）。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    db.query(models.TrainingPlan).filter(
        models.TrainingPlan.client_id == client.id,
        models.TrainingPlan.status == "active").update({"status": "archived"})
    plan = models.TrainingPlan(client_id=client.id, week_start=week_start,
                               days=generate_plan(client.goal), created_by=user.id)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


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
                user: models.User = Depends(auth_lib.get_current_user)):
    """手动调整训练计划：增删训练日、改时间、换动作，全量覆盖 days。"""
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
