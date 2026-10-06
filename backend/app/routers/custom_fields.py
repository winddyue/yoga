# -*- coding: utf-8 -*-
"""自定义字段路由：馆主可增减自定义字段（客户档案 / 评估记录两类）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/custom-fields", tags=["自定义字段"])


@router.get("", response_model=list[schemas.CustomFieldOut])
def list_fields(db: Session = Depends(get_db),
                _: models.User = Depends(auth_lib.get_current_user)):
    """自定义字段定义列表。"""
    return db.query(models.CustomFieldDef).all()


@router.post("", response_model=schemas.CustomFieldOut)
def create_field(data: schemas.CustomFieldIn,
                 db: Session = Depends(get_db),
                 _: models.User = Depends(auth_lib.require_owner)):
    """新增自定义字段（仅馆主）。"""
    f = models.CustomFieldDef(**data.model_dump())
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


@router.delete("/{field_id}")
def delete_field(field_id: int,
                 db: Session = Depends(get_db),
                 _: models.User = Depends(auth_lib.require_owner)):
    """删除自定义字段（仅馆主）。"""
    f = db.query(models.CustomFieldDef).filter(models.CustomFieldDef.id == field_id).first()
    if f:
        db.delete(f)
        db.commit()
    return {"ok": True}
