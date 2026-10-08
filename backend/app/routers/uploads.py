# -*- coding: utf-8 -*-
"""图片上传：打卡照片等。仅 jpg/png/webp，≤5MB。

注意：按项目隐私设计，上传目录不做 StaticFiles 静态挂载，
下载走鉴权的 /api/files/{filename}；本接口返回的 path 即该下载地址。
"""
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from .. import auth as auth_lib
from .. import models
from ..config import settings

router = APIRouter(prefix="/api", tags=["上传"])

ALLOWED = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_SIZE = 5 * 1024 * 1024


@router.post("/uploads")
def upload_image(file: UploadFile = File(...),
                 user: models.User = Depends(auth_lib.get_current_user)):
    """上传一张图片，返回 {"path": "/api/files/xxx.jpg"}（鉴权下载地址）。"""
    ext = ALLOWED.get(file.content_type or "")
    if not ext:
        # 再按扩展名宽容一次（部分客户端 content-type 不准）
        name = (file.filename or "").lower()
        for ct, e in ALLOWED.items():
            if name.endswith(e) or (e == ".jpg" and name.endswith(".jpeg")):
                ext = e
                break
    if not ext:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/webp 图片")
    data = file.file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")
    if not data:
        raise HTTPException(status_code=400, detail="空文件")
    filename = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(os.path.join(settings.UPLOAD_DIR, filename), "wb") as f:
        f.write(data)
    return {"path": f"/api/files/{filename}"}
