# -*- coding: utf-8 -*-
"""认证路由：登录、当前用户信息、用户管理（仅馆主可创建教练账号）。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=schemas.Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """用户名 + 密码登录，返回 JWT。"""
    user = db.query(models.User).filter(models.User.username == form.username).first()
    if not user or not auth_lib.verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已注销，请联系馆主")
    return {"access_token": auth_lib.create_access_token(user.username)}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(auth_lib.get_current_user)):
    """获取当前登录用户信息。"""
    return user


@router.post("/users", response_model=schemas.UserOut)
def create_user(data: schemas.UserCreate,
               db: Session = Depends(get_db),
               _: models.User = Depends(auth_lib.require_owner)):
    """创建用户（仅馆主）：添加教练账号，或为客户建登录账号（需绑定客户档案）。"""
    if data.role not in ("owner", "coach", "client"):
        raise HTTPException(status_code=400, detail="角色只能是 owner / coach / client")
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if data.role == "client":
        if not data.client_id or not db.query(models.Client).filter(
                models.Client.id == data.client_id).first():
            raise HTTPException(status_code=400, detail="客户账号需绑定有效的客户档案")
    user = models.User(username=data.username, password_hash=auth_lib.hash_password(data.password),
                       role=data.role, name=data.name, client_id=data.client_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db),
               _: models.User = Depends(auth_lib.require_owner)):
    """用户列表（仅馆主）。"""
    return db.query(models.User).all()
