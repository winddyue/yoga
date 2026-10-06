# -*- coding: utf-8 -*-
"""审计日志：关键写操作留痕。"""
from sqlalchemy.orm import Session

from .. import models


def log(db: Session, user_id: int, action: str,
        target_type: str = "", target_id: int = 0):
    """记录一条审计日志（失败不抛错，避免影响主流程）。"""
    try:
        db.add(models.AuditLog(user_id=user_id, action=action,
                               target_type=target_type, target_id=target_id))
        db.commit()
    except Exception:
        db.rollback()
