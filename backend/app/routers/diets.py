# -*- coding: utf-8 -*-
"""饮食方案路由：按公式自动生成、教练确认。

热量与营养素计算：BMR 用 Mifflin-St Jeor（体脂已知时用 Katch-McArdle），
TDEE = BMR × 活动系数，蛋白质按目标取 0.8–2.2g/kg，脂肪 0.6g/kg，碳水补足剩余。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db
from ..services.nutrition import calc_targets, generate_meals

router = APIRouter(prefix="/api", tags=["饮食方案"])


def _latest_assessment(db: Session, client_id: int):
    """取客户最新一次评估（没有则返回 None）。"""
    return (db.query(models.Assessment)
            .filter(models.Assessment.client_id == client_id)
            .order_by(models.Assessment.date.desc()).first())


@router.post("/clients/{client_id}/diets/generate", response_model=schemas.DietPlanOut)
def generate(client_id: int, data: schemas.DietGenerateIn,
             db: Session = Depends(get_db),
             user: models.User = Depends(auth_lib.require_staff)):
    """生成饮食方案：按最新评估 + 目标计算热量与营养素，给出三餐加餐搭配。仅工作人员可写。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    a = _latest_assessment(db, client_id)
    if not a or not a.weight_kg:
        raise HTTPException(status_code=400, detail="请先录入一次包含体重的评估记录")
    targets = calc_targets(a.weight_kg, client.height_cm or 160, client.age or 30,
                           client.gender or "女", client.goal, data.activity_level,
                           a.body_fat_pct or None)
    diet = models.DietPlan(
        client_id=client.id, date=data.date,
        meals=generate_meals(targets["calories_target"]),
        calories_target=targets["calories_target"],
        protein_g=targets["protein_g"], fat_g=targets["fat_g"], carbs_g=targets["carbs_g"],
        status="pending",
    )
    db.add(diet)
    db.commit()
    db.refresh(diet)
    return diet


@router.get("/clients/{client_id}/diets", response_model=list[schemas.DietPlanOut])
def list_diets(client_id: int,
               db: Session = Depends(get_db),
               user: models.User = Depends(auth_lib.get_current_user)):
    """客户的饮食方案列表。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    return (db.query(models.DietPlan)
            .filter(models.DietPlan.client_id == client.id)
            .order_by(models.DietPlan.date.desc()).all())


@router.post("/diets/{diet_id}/confirm", response_model=schemas.DietPlanOut)
def confirm(diet_id: int,
            db: Session = Depends(get_db),
            user: models.User = Depends(auth_lib.require_staff)):
    """教练确认饮食方案：确认后的方案作为后续推荐的学习依据。仅工作人员可写。"""
    diet = db.query(models.DietPlan).filter(models.DietPlan.id == diet_id).first()
    if not diet:
        raise HTTPException(status_code=404, detail="方案不存在")
    auth_lib.client_visible_to(db, user, diet.client_id)
    diet.status = "confirmed"
    diet.confirmed_by = user.id
    db.commit()
    db.refresh(diet)
    return diet


@router.get("/clients/{client_id}/diets/confirmed")
def confirmed_meals(client_id: int,
                    db: Session = Depends(get_db),
                    user: models.User = Depends(auth_lib.get_current_user)):
    """已确认过的饮食方案（供后续推荐学习参考：取最近 5 条）。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    rows = (db.query(models.DietPlan)
            .filter(models.DietPlan.client_id == client.id,
                    models.DietPlan.status == "confirmed")
            .order_by(models.DietPlan.date.desc()).limit(5).all())
    return [{"date": r.date, "meals": r.meals} for r in rows]
