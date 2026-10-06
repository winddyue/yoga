# -*- coding: utf-8 -*-
"""认证：密码哈希、JWT 签发与校验、角色守卫。"""
import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .database import get_db

# 密码哈希上下文（bcrypt）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# 从请求头 Authorization: Bearer <token> 取 token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    """明文密码 -> 哈希（入库只存哈希）。"""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """登录时校验密码。"""
    return pwd_context.verify(plain, hashed)


def create_access_token(username: str) -> str:
    """签发 JWT。"""
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode({"sub": username, "exp": expire}, settings.SECRET_KEY, algorithm="HS256")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    """从 token 解析当前用户；token 无效则 401。"""
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
    except JWTError:
        raise exc
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise exc
    return user


def require_owner(user: models.User = Depends(get_current_user)) -> models.User:
    """仅馆主可访问的接口守卫。"""
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="仅馆主可操作")
    return user


def client_visible_to(db: Session, user: models.User, client_id: int) -> models.Client:
    """按角色判断客户是否可见：馆主看全馆，教练只看自己的客户。"""
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="客户不存在")
    if user.role != "owner" and client.coach_id != user.id:
        raise HTTPException(status_code=403, detail="无权查看该客户")
    return client
