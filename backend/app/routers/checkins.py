# -*- coding: utf-8 -*-
"""每日打卡：训练/饮食二选一，每天每种一次，可附照片。

客户只能给自己打卡；工作人员可带 ?client_id= 代打卡。
"""
import datetime
import os

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api", tags=["打卡"])

KINDS = ("training", "diet")


def _today() -> str:
    return datetime.date.today().isoformat()


def _resolve_client(db: Session, user: models.User,
                    client_id: int | None) -> models.Client:
    """打卡归属客户：客户只能是自己；staff 必须显式传 client_id 代打卡。"""
    if user.role == "client":
        return auth_lib.get_own_client(db, user)
    if not client_id:
        raise HTTPException(status_code=400, detail="请指定客户 client_id")
    return auth_lib.client_visible_to(db, user, client_id)


@router.post("/checkins", response_model=schemas.CheckinOut)
def create_checkin(data: schemas.CheckinIn,
                   client_id: int | None = Query(default=None),
                   db: Session = Depends(get_db),
                   user: models.User = Depends(auth_lib.get_current_user)):
    """打卡一次。重复打卡（同一客户同一天同一种）→ 400。"""
    if data.kind not in KINDS:
        raise HTTPException(status_code=400, detail="kind 只能是 training 或 diet")
    client = _resolve_client(db, user, client_id)
    date = data.date or _today()
    photo_path = data.photo_path or ""
    if photo_path:
        # 只接受本服务上传目录内的文件，防任意路径
        base = os.path.basename(photo_path)
        full = os.path.join(settings.UPLOAD_DIR, base)
        if not os.path.isfile(full):
            raise HTTPException(status_code=400, detail="照片不存在，请先上传")
        photo_path = f"/api/files/{base}"
    c = models.DailyCheckin(client_id=client.id, date=date, kind=data.kind,
                            note=data.note or "", photo_path=photo_path)
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="今日已打卡")
    db.refresh(c)
    return c


def _by_month(db: Session, client_id: int, ym: str):
    q = (db.query(models.DailyCheckin)
         .filter(models.DailyCheckin.client_id == client_id))
    if ym:
        q = q.filter(models.DailyCheckin.date.like(f"{ym}%"))
    return q.order_by(models.DailyCheckin.date.desc()).all()


@router.get("/checkins/mine", response_model=list[schemas.CheckinOut])
def my_checkins(ym: str = Query(default=""),
                db: Session = Depends(get_db),
                user: models.User = Depends(auth_lib.get_current_user)):
    """当前客户按月查自己的打卡。ym 如 2026-10，空则默认本月。"""
    client = auth_lib.get_own_client(db, user)
    return _by_month(db, client.id, ym or _today()[:7])


@router.get("/clients/{client_id}/checkins", response_model=list[schemas.CheckinOut])
def client_checkins(client_id: int, ym: str = Query(default=""),
                    db: Session = Depends(get_db),
                    user: models.User = Depends(auth_lib.get_current_user)):
    """工作人员看客户打卡（客户看自己，他人 403）。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    return _by_month(db, client.id, ym or _today()[:7])
