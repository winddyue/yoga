# -*- coding: utf-8 -*-
"""认证路由：登录、微信登录、当前用户信息、用户管理（仅馆主可创建教练账号）。"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["认证"])


class WxLoginIn(BaseModel):
    code: str  # wx.login 拿到的临时凭证


def _code2session(code: str) -> str:
    """wx.login code -> openid。调用微信 code2session 接口。

    本地开发/CI 无真实微信环境时，可设 WX_DEV_MOCK=true，
    用 "mock:任意标识" 作为 code 换取 mock openid（生产禁止）。
    """
    if settings.WX_DEV_MOCK and code.startswith("mock:"):
        return "mock_openid_" + code[5:]
    if not settings.WX_APPID or not settings.WX_SECRET:
        raise HTTPException(status_code=400,
                            detail="服务器未配置微信 AppID/Secret（WX_APPID/WX_SECRET）")
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {"appid": settings.WX_APPID, "secret": settings.WX_SECRET,
              "js_code": code, "grant_type": "authorization_code"}
    try:
        resp = httpx.get(url, params=params, timeout=10)
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="微信登录服务暂不可用，请稍后重试")
    if data.get("errcode"):
        # 40029 无效 code 等，统一提示重新拉起登录
        raise HTTPException(status_code=400, detail="微信登录凭证无效，请重试")
    openid = data.get("openid")
    if not openid:
        raise HTTPException(status_code=502, detail="微信登录失败：未返回 openid")
    return openid


@router.post("/wx-login", response_model=schemas.Token)
def wx_login(data: WxLoginIn, db: Session = Depends(get_db)):
    """微信免密登录：code 换 openid，已绑定的账号直接签发 JWT。"""
    openid = _code2session(data.code)
    binding = (db.query(models.WxBinding)
               .filter(models.WxBinding.openid == openid).first())
    if not binding:
        raise HTTPException(status_code=404,
                            detail="该微信尚未绑定账号，请先用账号密码登录并自动绑定")
    user = db.query(models.User).filter(models.User.id == binding.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="账号已注销，请联系馆主")
    return {"access_token": auth_lib.create_access_token(user.username)}


@router.post("/wx-bind")
def wx_bind(data: WxLoginIn, db: Session = Depends(get_db),
            user: models.User = Depends(auth_lib.get_current_user)):
    """绑定微信：登录态下把当前账号与 wx.login 的 openid 关联，之后可免密登录。"""
    openid = _code2session(data.code)
    # openid 已被其他账号绑定：拒绝，防止一个微信绑多个账号造成串号
    exist = (db.query(models.WxBinding)
             .filter(models.WxBinding.openid == openid).first())
    if exist and exist.user_id != user.id:
        raise HTTPException(status_code=400, detail="该微信已绑定其他账号")
    if not exist:
        db.add(models.WxBinding(user_id=user.id, openid=openid))
        db.commit()
    return {"ok": True, "bound": True}


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
