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
    if not user.is_active:
        # 已注销账号的旧 token 立即失效
        raise exc
    return user


def require_owner(user: models.User = Depends(get_current_user)) -> models.User:
    """仅馆主可访问的接口守卫。"""
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="仅馆主可操作")
    return user


def require_staff(user: models.User = Depends(get_current_user)) -> models.User:
    """馆主或教练可访问（客户不可）。"""
    if user.role not in ("owner", "coach"):
        raise HTTPException(status_code=403, detail="仅工作人员可操作")
    return user


def get_own_client(db: Session, user: models.User) -> models.Client:
    """客户角色：取自己关联的客户档案；未绑定则 404。"""
    if user.role != "client" or not user.client_id:
        raise HTTPException(status_code=403, detail="仅客户账号可操作")
    client = db.query(models.Client).filter(models.Client.id == user.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="未绑定客户档案")
    return client


def client_visible_to(db: Session, user: models.User, client_id: int) -> models.Client:
    """按角色判断客户是否可见：
    馆主看全馆，教练只看自己的客户，客户只看自己的档案。"""
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="客户不存在")
    if user.role == "owner":
        return client
    if user.role == "coach" and client.coach_id == user.id:
        return client
    if user.role == "client" and user.client_id == client_id:
        return client
    raise HTTPException(status_code=403, detail="无权查看该客户")


# 客户角色不可见的敏感字段（教练内部备注等）
CLIENT_HIDDEN_FIELDS = {"notes"}


def filter_client_for_role(client: models.Client, user: models.User) -> dict:
    """字段级权限：客户角色看不到敏感字段。返回可序列化的字典。"""
    data = {
        "id": client.id, "name": client.name, "gender": client.gender,
        "age": client.age, "height_cm": client.height_cm, "phone": client.phone,
        "goal": client.goal, "coach_id": client.coach_id,
        "custom_values": client.custom_values or {},
        "attendance_rate": client.attendance_rate or 0,
        "is_minor": client.is_minor,
    }
    if user.role != "client":
        data["notes"] = client.notes or ""
    return data


def require_sensitive_consent(db: Session, client: models.Client):
    """敏感信息录入前校验：需有单独同意记录；14 岁以下需监护人同意。"""
    consent = (db.query(models.Consent)
               .filter(models.Consent.client_id == client.id,
                       models.Consent.consent_type == "sensitive_info").first())
    if not consent:
        raise HTTPException(status_code=400, detail="需先完成敏感信息单独授权（合规要求）")
    if client.age and client.age < 14 and not client.guardian_consent:
        raise HTTPException(status_code=400, detail="未满 14 岁，需监护人同意后方可录入")
