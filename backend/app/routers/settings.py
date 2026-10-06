# -*- coding: utf-8 -*-
"""设置路由：第三方 API 配置。

安全原则：密钥只从服务器环境变量读取，前端只能看到“是否已配置”，
永远拿不到明文；接口地址、模型名等非密钥配置可在此修改。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api/settings", tags=["设置"])

# 允许在设置页修改的非密钥项
EDITABLE = ("ocr_api_url", "ai_api_url", "ai_model")


def _stored(db: Session, key: str, fallback: str) -> str:
    """读配置：数据库优先，没有则回退到环境变量默认值。"""
    row = db.query(models.Setting).filter(models.Setting.key == key).first()
    return row.value if row else fallback


@router.get("", response_model=schemas.SettingsOut)
def get_settings(db: Session = Depends(get_db),
                 _: models.User = Depends(auth_lib.require_owner)):
    """获取第三方 API 配置（仅馆主；密钥只返回配置状态）。"""
    return {
        "ocr_api_url": _stored(db, "ocr_api_url", settings.OCR_API_URL),
        "ai_api_url": _stored(db, "ai_api_url", settings.AI_API_URL),
        "ai_model": _stored(db, "ai_model", settings.AI_MODEL),
        "ocr_configured": bool(settings.OCR_API_KEY),
        "ai_configured": bool(settings.AI_API_KEY),
    }


@router.put("")
def update_settings(data: schemas.SettingsIn,
                    db: Session = Depends(get_db),
                    _: models.User = Depends(auth_lib.require_owner)):
    """更新非密钥配置（仅馆主）。"""
    for key in EDITABLE:
        value = getattr(data, key)
        if value is not None:
            row = db.query(models.Setting).filter(models.Setting.key == key).first()
            if row:
                row.value = value
            else:
                db.add(models.Setting(key=key, value=value))
    db.commit()
    return {"ok": True}
