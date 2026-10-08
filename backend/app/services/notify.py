# -*- coding: utf-8 -*-
"""站内通知：一期只做站内通知中心，二期再接微信订阅消息。

微信订阅消息（message.subscribe.send）需要馆主在小程序后台申请消息模板
并配置模板 ID，本次只预留本 helper 的调用点，届时在此统一加发微信推送。
"""
from sqlalchemy.orm import Session

from .. import models


def notify(db: Session, user_id: int, type: str, title: str, body: str,
           ref_type: str = "", ref_id: int = 0) -> models.Notification:
    """写一条站内通知。user_id 为接收人的 users.id。"""
    n = models.Notification(
        user_id=user_id, type=type, title=title, body=body,
        ref_type=ref_type, ref_id=ref_id,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def _client_user_id(db: Session, client_id: int) -> int | None:
    """客户档案 -> 其登录账号的 user_id（客户可能没有账号）。"""
    u = (db.query(models.User)
         .filter(models.User.client_id == client_id,
                 models.User.is_active == True).first())  # noqa: E712
    return u.id if u else None


def notify_client(db: Session, client_id: int, type: str, title: str,
                  body: str, ref_type: str = "", ref_id: int = 0):
    """给客户发通知（有登录账号才发，没有则静默跳过）。"""
    uid = _client_user_id(db, client_id)
    if uid:
        notify(db, uid, type, title, body, ref_type, ref_id)


def notify_coach(db: Session, client_id: int, type: str, title: str,
                 body: str, ref_type: str = "", ref_id: int = 0):
    """给客户的所属教练发通知（无教练则跳过）。"""
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if client and client.coach_id:
        coach = (db.query(models.User)
                 .filter(models.User.id == client.coach_id,
                         models.User.is_active == True).first())  # noqa: E712
        if coach:
            notify(db, coach.id, type, title, body, ref_type, ref_id)
