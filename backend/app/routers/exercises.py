# -*- coding: utf-8 -*-
"""动作库路由：训练计划编排时点选动作（静态列表）。"""
from fastapi import APIRouter, Depends

from .. import auth as auth_lib
from .. import models
from ..data.exercises import CATEGORIES, EXERCISES

router = APIRouter(prefix="/api", tags=["动作库"])


@router.get("/exercises")
def list_exercises(user: models.User = Depends(auth_lib.get_current_user)):
    """动作库列表（登录即可）：[{name, category, muscle}]。"""
    return {"categories": CATEGORIES, "exercises": EXERCISES}
