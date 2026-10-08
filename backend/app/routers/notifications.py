# -*- coding: utf-8 -*-
"""站内通知中心：列表 / 未读数 / 标已读 / 全部已读。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/notifications", tags=["通知"])


@router.get("", response_model=list[schemas.NotificationOut])
def list_notifications(limit: int = Query(20, le=100),
                       offset: int = Query(0, ge=0),
                       db: Session = Depends(get_db),
                       user: models.User = Depends(auth_lib.get_current_user)):
    """通知列表：未读优先，再按时间倒序。只能看自己的。"""
    rows = (db.query(models.Notification)
            .filter(models.Notification.user_id == user.id)
            .order_by(models.Notification.is_read.asc(),
                      models.Notification.created_at.desc())
            .offset(offset).limit(limit).all())
    return rows


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db),
                 user: models.User = Depends(auth_lib.get_current_user)):
    """未读通知数（供小铃铛 badge / 小程序红点）。"""
    n = (db.query(models.Notification)
         .filter(models.Notification.user_id == user.id,
                 models.Notification.is_read == False).count())  # noqa: E712
    return {"unread": n}


@router.post("/{nid}/read")
def mark_read(nid: int,
              db: Session = Depends(get_db),
              user: models.User = Depends(auth_lib.get_current_user)):
    """标一条为已读（只能标自己的）。"""
    n = (db.query(models.Notification)
         .filter(models.Notification.id == nid,
                 models.Notification.user_id == user.id).first())
    if not n:
        raise HTTPException(status_code=404, detail="通知不存在")
    n.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.get_current_user)):
    """全部标为已读。"""
    (db.query(models.Notification)
     .filter(models.Notification.user_id == user.id,
             models.Notification.is_read == False)  # noqa: E712
     .update({"is_read": True}, synchronize_session=False))
    db.commit()
    return {"ok": True}
