# -*- coding: utf-8 -*-
"""评估路由：新增/查询评估记录、趋势数据、照片上传、OCR 识别预留。"""
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..services import ocr as ocr_service
from ..services.training import health_warnings

router = APIRouter(prefix="/api", tags=["评估"])

# 允许上传的图片类型
ALLOWED_IMG = {"image/jpeg", "image/png", "image/webp"}


@router.post("/clients/{client_id}/assessments", response_model=schemas.AssessmentOut)
def create_assessment(client_id: int, data: schemas.AssessmentIn,
                      db: Session = Depends(get_db),
                      user: models.User = Depends(auth_lib.get_current_user)):
    """新增一次评估记录。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    a = models.Assessment(client_id=client.id, **data.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.get("/clients/{client_id}/assessments", response_model=list[schemas.AssessmentOut])
def list_assessments(client_id: int,
                     db: Session = Depends(get_db),
                     user: models.User = Depends(auth_lib.get_current_user)):
    """某客户的评估记录（按日期倒序）。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    return (db.query(models.Assessment)
            .filter(models.Assessment.client_id == client.id)
            .order_by(models.Assessment.date.desc()).all())


@router.get("/clients/{client_id}/trends")
def trends(client_id: int,
           db: Session = Depends(get_db),
           user: models.User = Depends(auth_lib.get_current_user)):
    """趋势数据：返回按日期正序的体重/体脂序列，供前端画曲线。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    rows = (db.query(models.Assessment)
            .filter(models.Assessment.client_id == client.id)
            .order_by(models.Assessment.date.asc()).all())
    return {
        "dates": [r.date for r in rows],
        "weight": [r.weight_kg for r in rows],
        "body_fat": [r.body_fat_pct for r in rows],
    }


@router.get("/clients/{client_id}/warnings")
def warnings(client_id: int,
             db: Session = Depends(get_db),
             user: models.User = Depends(auth_lib.get_current_user)):
    """健康风险提示：基于最新一次评估生成（仅提示，不做医疗诊断）。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    latest = (db.query(models.Assessment)
              .filter(models.Assessment.client_id == client.id)
              .order_by(models.Assessment.date.desc()).first())
    if not latest:
        return {"warnings": []}
    return {"warnings": health_warnings(latest)}


@router.post("/clients/{client_id}/photo")
def upload_photo(client_id: int, file: UploadFile = File(...),
                 db: Session = Depends(get_db),
                 user: models.User = Depends(auth_lib.get_current_user)):
    """上传体测单照片：保存到本地 uploads 目录，返回路径供评估记录引用。"""
    auth_lib.client_visible_to(db, user, client_id)
    if file.content_type not in ALLOWED_IMG:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/WebP 图片")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    name = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(settings.UPLOAD_DIR, name)
    with open(path, "wb") as f:
        f.write(file.file.read())
    return {"photo_path": path}


@router.post("/ocr-extract")
def ocr_extract(file: UploadFile = File(...),
                _: models.User = Depends(auth_lib.get_current_user)):
    """拍照识别预留接口：当前未对接具体 OCR 供应商，返回明确提示。"""
    try:
        data = ocr_service.extract_assessment_from_image(file.file.read())
        return {"ok": True, "data": data}
    except ocr_service.OcrNotConfigured as e:
        raise HTTPException(status_code=501, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
