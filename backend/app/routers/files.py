# -*- coding: utf-8 -*-
"""鉴权文件下载：替代原来无鉴权的 /uploads 静态挂载。

体测单照片等健康资料属敏感信息，下载前按角色校验可见性：
馆主可下全部，教练只能下名下客户的，客户只能下自己的。
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api/files", tags=["文件"])


def _safe_path(filename: str) -> str:
    """文件名安全校验：只允许纯文件名，防目录穿越。"""
    base = os.path.basename(filename or "")
    if not base or base != filename or base.startswith("."):
        raise HTTPException(status_code=400, detail="非法文件名")
    full = os.path.join(settings.UPLOAD_DIR, base)
    # 双重保险：解析后仍必须在上传目录内
    if os.path.commonpath([os.path.abspath(full),
                           os.path.abspath(settings.UPLOAD_DIR)]) != os.path.abspath(settings.UPLOAD_DIR):
        raise HTTPException(status_code=400, detail="非法文件名")
    return full


@router.get("/{filename}")
def download_file(filename: str,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.get_current_user)):
    """下载上传文件（鉴权）：按引用该文件的评估记录归属校验可见性。"""
    full = _safe_path(filename)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="文件不存在")
    # 找到引用该文件的评估记录，归属哪个客户
    like = f"%{os.path.basename(filename)}%"
    assessment = (db.query(models.Assessment)
                  .filter(models.Assessment.photo_path.like(like)).first())
    if assessment:
        # 按客户归属校验：馆主全看，教练看名下，客户看自己
        auth_lib.client_visible_to(db, user, assessment.client_id)
    elif user.role not in ("owner", "coach"):
        # 无归属记录的文件仅工作人员可下
        raise HTTPException(status_code=403, detail="无权下载该文件")
    return FileResponse(full)
