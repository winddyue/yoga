# -*- coding: utf-8 -*-
"""应用入口：创建 FastAPI 应用、挂载路由、初始化数据库与默认账号。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import models
from .auth import hash_password
from .config import settings
from .database import Base, SessionLocal, engine
from .routers import assessments, auth, clients, custom_fields, dashboard, diets, plans, settings as settings_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时：建表、建上传目录、首次启动自动创建默认馆主账号。"""
    Base.metadata.create_all(bind=engine)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            db.add(models.User(username=settings.ADMIN_USERNAME,
                               password_hash=hash_password(settings.ADMIN_PASSWORD),
                               role="owner", name="馆主"))
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="瑜伽馆/健身房客户管理", version="0.1.0", lifespan=lifespan)

# 跨域：允许前端开发服务器与同域部署访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 上传文件静态访问（目录必须在挂载前存在）
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# 挂载全部路由
app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(custom_fields.router)
app.include_router(assessments.router)
app.include_router(plans.router)
app.include_router(diets.router)
app.include_router(settings_router.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def seed_admin():
    """首次启动自动创建默认馆主账号（用户表为空时）。"""
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            db.add(models.User(username=settings.ADMIN_USERNAME,
                               password_hash=hash_password(settings.ADMIN_PASSWORD),
                               role="owner", name="馆主"))
            db.commit()
    finally:
        db.close()


@app.get("/api/health")
def health():
    """健康检查。"""
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
