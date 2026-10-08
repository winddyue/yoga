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
from ..services import ai_gate, llm
from ..services import notify as notify_service
from ..services.nutrition import calc_targets, generate_meals, targets as nutrition_targets
import datetime

router = APIRouter(prefix="/api", tags=["饮食方案"])

DISCLAIMER = "AI 生成内容仅供参考，不构成医疗建议，请遵医嘱"


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


@router.get("/clients/{client_id}/nutrition-targets")
def get_nutrition_targets(client_id: int,
                         db: Session = Depends(get_db),
                         user: models.User = Depends(auth_lib.get_current_user)):
    """热量与宏量目标（Mifflin 公式）：{bmr, tdee, calories_target, protein_g, fat_g, carbs_g, note}。

    用客户档案（性别/年龄/身高/目标）+ 最新体重计算；档案信息不全时 400。
    """
    client = auth_lib.client_visible_to(db, user, client_id)
    a = _latest_assessment(db, client_id)
    weight = a.weight_kg if a and a.weight_kg else None
    t = nutrition_targets(client.gender, client.age, client.height_cm,
                          weight, client.goal or "")
    if t is None:
        raise HTTPException(status_code=400, detail="档案信息不全：需要性别/年龄/身高/体重")
    return t


@router.post("/clients/{client_id}/diets/ai-generate",
            response_model=schemas.DietPlanOut)
def ai_generate(client_id: int,
                db: Session = Depends(get_db),
                user: models.User = Depends(auth_lib.get_current_user)):
    """AI 饮食双轨制·快轨：AI 即时生成饮食初稿（status=ai_draft，待教练确认）。

    权限：客户只能给自己生成；教练/馆主可为名下可见客户生成。
    走 AI 准入（套餐功能 + 月额度）并记录用量。LLM 未配置时返回 503，
    不静默降级为模板。生成后通知客户与所属教练。
    """
    client = auth_lib.client_visible_to(db, user, client_id)
    ai_gate.check_ai_access(db, user, feature="plan_diet")
    a = _latest_assessment(db, client_id)
    if not a or not a.weight_kg:
        raise HTTPException(status_code=400, detail="请先录入一次包含体重的评估记录")
    prefs = (client.custom_values or {}).get("diet_preferences", "")
    profile = {
        "name": client.name, "gender": client.gender or "女",
        "age": client.age or 30, "height_cm": client.height_cm or 160,
        "weight_kg": a.weight_kg, "body_fat_pct": a.body_fat_pct or "",
        "waist_cm": a.waist_cm or "", "goal": client.goal or "减脂",
        "preferences": prefs,
    }
    try:
        plan = llm.generate_diet_plan(profile)
    except llm.LlmNotConfigured:
        raise HTTPException(status_code=503, detail="馆主尚未配置 AI 服务，请联系馆主")
    ai_gate.record_usage(db, user.id, kind="plan_diet")
    diet = models.DietPlan(
        client_id=client.id,
        date=datetime.date.today().isoformat(),
        meals=plan["meals"],
        calories_target=plan["calories_target"],
        protein_g=plan["protein_g"], fat_g=plan["fat_g"], carbs_g=plan["carbs_g"],
        status="ai_draft", source="ai",
    )
    db.add(diet)
    db.commit()
    db.refresh(diet)
    # 通知：客户（AI 初稿已生成）+ 教练（待确认）
    notify_service.notify_client(
        db, client.id, "diet_ai_ready",
        "AI 饮食建议已生成",
        f"{client.name}，你的 AI 饮食建议已生成（待教练确认），可先参考",
        ref_type="diet", ref_id=diet.id)
    notify_service.notify_coach(
        db, client.id, "diet_ai_ready",
        "AI 饮食初稿待确认",
        f"{client.name} 的 AI 饮食初稿已生成，请确认或微调",
        ref_type="diet", ref_id=diet.id)
    diet.disclaimer = DISCLAIMER  # 非入库属性，仅随响应返回
    return diet


@router.get("/diets/pending")
def pending_diets(db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.require_staff)):
    """待确认饮食方案（含 AI 初稿）：教练看自己客户，馆主看全馆。"""
    q = (db.query(models.DietPlan, models.Client.name)
         .join(models.Client, models.Client.id == models.DietPlan.client_id)
         .filter(models.DietPlan.status.in_(("pending", "ai_draft"))))
    if user.role != "owner":
        q = q.filter(models.Client.coach_id == user.id)
    rows = q.order_by(models.DietPlan.created_at.desc()).all()
    return [{
        "id": d.id, "client_id": d.client_id, "client_name": name,
        "date": d.date, "meals": d.meals,
        "calories_target": d.calories_target, "protein_g": d.protein_g,
        "fat_g": d.fat_g, "carbs_g": d.carbs_g,
        "status": d.status, "source": d.source or "coach",
    } for d, name in rows]


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
def confirm(diet_id: int, data: schemas.DietConfirmIn | None = None,
            db: Session = Depends(get_db),
            user: models.User = Depends(auth_lib.require_staff)):
    """教练确认饮食方案：可附带微调后的 meals；确认后通知客户。

    双轨制准轨：AI 初稿（ai_draft）经此确认转为 confirmed。
    仅工作人员可写，客户调用 403。"""
    diet = db.query(models.DietPlan).filter(models.DietPlan.id == diet_id).first()
    if not diet:
        raise HTTPException(status_code=404, detail="方案不存在")
    client = auth_lib.client_visible_to(db, user, diet.client_id)
    if data and data.meals:
        diet.meals = data.meals
    diet.status = "confirmed"
    diet.confirmed_by = user.id
    db.commit()
    db.refresh(diet)
    notify_service.notify_client(
        db, client.id, "diet_confirmed",
        "教练已确认你的饮食方案",
        f"{client.name}，教练已确认你的饮食方案，可以开始执行了",
        ref_type="diet", ref_id=diet.id)
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
