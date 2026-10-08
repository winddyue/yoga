# -*- coding: utf-8 -*-
"""应用入口：创建 FastAPI 应用、挂载路由、初始化数据库与默认账号。"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, update

from . import models
from .auth import hash_password
from .config import settings, validate_prod
from .database import Base, SessionLocal, engine
from .routers import assessments, auth, bookings, checkins, clients, consents, custom_fields, dashboard, diets, exercises, files, intake, notifications, plans, settings as settings_router, subscriptions, uploads


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时：生产安全检查、建表、建上传目录、首次启动自动创建默认馆主账号、
    预置 AI 套餐。"""
    validate_prod()  # 生产模式下密钥未配置则直接报错退出
    Base.metadata.create_all(bind=engine)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            db.add(models.User(username=settings.ADMIN_USERNAME,
                               password_hash=hash_password(settings.ADMIN_PASSWORD),
                               role="owner", name="馆主"))
            db.commit()
        from .services import ai_gate
        ai_gate.ensure_default_plans(db)
        # 座位计数器自愈：老库已有预约数据但 booked_seats 未回填/过期时，
        # 按实际有效预约数（booked + checked_in）校准，保证预约关口
        # 不因计数器过期而超卖。幂等，多实例同时启动也安全。
        # 列本身由 backend/alembic 迁移补齐（0001_booking_seats）；
        # 列不存在时跳过，避免老库启动报错。
        # 正式的表结构迁移见 backend/alembic（0001_booking_seats）。
        from sqlalchemy import inspect as _sa_inspect
        _cols = {c["name"] for c in
                 _sa_inspect(db.get_bind()).get_columns("courses")}
        if "booked_seats" in _cols:
            db.execute(
                update(models.Course).values(
                    booked_seats=(
                        select(func.count(models.Booking.id))
                        .where(models.Booking.course_id == models.Course.id,
                               models.Booking.status.in_(("booked", "checked_in")))
                        .scalar_subquery())))
            db.commit()
    finally:
        db.close()
    yield


app = FastAPI(title="瑜伽馆/健身房客户管理", version="0.3.0", lifespan=lifespan)

# 跨域：白名单从环境变量 CORS_ORIGINS 读取（逗号分隔），默认仅本地开发源
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注意：上传目录不再静态挂载，文件下载走 /api/files/{filename} 鉴权接口
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# 挂载全部路由
app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(custom_fields.router)
app.include_router(assessments.router)
app.include_router(plans.router)
app.include_router(diets.router)
app.include_router(exercises.router)
app.include_router(settings_router.router)
app.include_router(dashboard.router)
app.include_router(bookings.router)
app.include_router(intake.router)
app.include_router(notifications.router)
app.include_router(subscriptions.router)
app.include_router(consents.router)
app.include_router(files.router)
app.include_router(checkins.router)
app.include_router(uploads.router)


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
