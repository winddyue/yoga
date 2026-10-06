# -*- coding: utf-8 -*-
"""经营概况路由：馆主看全馆数据（客户数、教练数、本周新增评估等极简指标）。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models
from ..database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["经营概况"])


@router.get("")
def overview(db: Session = Depends(get_db),
             user: models.User = Depends(auth_lib.get_current_user)):
    """经营概况：馆主看全馆，教练看自己的客户。"""
    q = db.query(models.Client)
    if user.role != "owner":
        q = q.filter(models.Client.coach_id == user.id)
    clients = q.all()
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    recent_assessments = (db.query(models.Assessment)
                          .filter(models.Assessment.client_id.in_([c.id for c in clients] or [0]),
                                   models.Assessment.date >= week_ago).count())
    pending_diets = (db.query(models.DietPlan)
                     .filter(models.DietPlan.client_id.in_([c.id for c in clients] or [0]),
                              models.DietPlan.status == "pending").count())
    return {
        "client_count": len(clients),
        "coach_count": db.query(models.User).filter(models.User.role == "coach").count(),
        "week_assessments": recent_assessments,
        "pending_diets": pending_diets,  # 待确认的饮食方案数
    }
