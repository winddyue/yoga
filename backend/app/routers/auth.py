# -*- coding: utf-8 -*-
"""认证路由：登录、微信登录、当前用户信息、用户管理（仅馆主可创建教练账号）。"""
import hashlib
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..services import crypto as crypto_service

router = APIRouter(prefix="/api/auth", tags=["认证"])


class WxLoginIn(BaseModel):
    code: str  # wx.login 拿到的临时凭证


class WxRegisterIn(BaseModel):
    """微信一键注册：姓名必填（用于建档与点名），手机号可选（教练可事后补录）。"""
    code: str
    name: str = ""
    phone: str = ""

class ClientRegisterIn(BaseModel):
    name: str
    username: str
    password: str


class PhoneRegisterIn(BaseModel):
    """手机号快捷注册/登录。

    手机号来源由 code 决定：
      - "mock:11位手机号"：仅 WX_DEV_MOCK=true 时可用（本地联调）
      - 其它值：当作微信 getPhoneNumber 的 code 换取手机号（需企业主体 + 已配 AppSecret）
    注意：短信验证码方式尚未实现（见 _get_phone_by_code 的 TODO）。
    """
    code: str            # getPhoneNumber 的 code，或 mock:手机号
    phone: str = ""      # 预留：短信验证码方式直接传手机号（未实现）
    name: str = ""       # 可选，首次注册作为姓名
    wx_code: str = ""    # wx.login 的 code，注册时顺带绑定微信实现免密登录


def _code2session(code: str) -> str:
    """wx.login code -> openid。调用微信 code2session 接口。

    本地开发/CI 无真实微信环境时，可设 WX_DEV_MOCK=true，
    用 "mock:任意标识" 作为 code 换取 mock openid（生产禁止）。
    """
    if settings.WX_DEV_MOCK and code.startswith("mock:"):
        return "mock_openid_" + code[5:]
    if code.startswith("mock:"):
        # 前端处于开发版会自动发 mock: code；后端未开模拟时给出可操作的提示，
        # 不要笼统说"未配置 AppID"，否则会误导排查方向。
        raise HTTPException(status_code=400,
                            detail="本地模拟登录已禁用（后端 WX_DEV_MOCK=false），请改用账号密码登录")
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


def _get_phone_by_code(code: str) -> str:
    """getPhoneNumber 的 code -> 手机号。

    开发：WX_DEV_MOCK=true 时接受 "mock:11位手机号" 直接取号，方便本地无真实微信环境时联调。

    TODO: 生产路径未实现。需要先拿 access_token（GET /cgi-bin/token，
    用 appid+secret，应带缓存，有效期 7200s），再调
    POST https://api.weixin.qq.com/wxa/business/getuserphonenumber
    传 {"code": code} 取 phone_info.purePhoneNumber。
    另外该接口要求小程序主体为企业/组织，个人主体无法获取手机号。
    """
    if settings.WX_DEV_MOCK and code.startswith("mock:"):
        raw = code[5:].strip()
        # mock:13800000000 -> 13800000000；非合法手机号一律拒绝，避免脏数据
        if raw.isdigit() and len(raw) == 11 and raw.startswith("1"):
            return raw
        raise HTTPException(status_code=400, detail="模拟手机号格式不正确，请填 11 位手机号")
    if code.startswith("mock:"):
        raise HTTPException(status_code=400,
                            detail="本地模拟登录已禁用（后端 WX_DEV_MOCK=false），请改用账号密码登录")
    if not settings.WX_APPID or not settings.WX_SECRET:
        raise HTTPException(status_code=400,
                            detail="服务器未配置微信 AppID/Secret（WX_APPID/WX_SECRET）")
    raise HTTPException(status_code=501, detail="手机号快捷登录尚未接入，请先用账号密码登录")


def _phone_ok(phone: str) -> bool:
    """简单校验：11 位数字且以 1 开头。"""
    return bool(phone) and len(phone) == 11 and phone.isdigit() and phone.startswith("1")


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


@router.post("/wx-register", response_model=schemas.Token)
def wx_register(data: WxRegisterIn, db: Session = Depends(get_db)):
    """微信一键注册：新用户只需填姓名（手机号可选），即刻建档并绑定微信。

    这是客户的主路径：点「微信一键登录」发现未绑定 → 填个姓名 → 完成，
    之后每次打开都靠 openid 免密登录，用户全程不需要记密码。
    已绑定过的微信直接返回 token（等价于登录），保证重复点击不会重复建号。
    """
    openid = _code2session(data.code)

    # 已绑定：直接登录，不重复建档
    binding = (db.query(models.WxBinding)
               .filter(models.WxBinding.openid == openid).first())
    if binding:
        user = db.query(models.User).filter(models.User.id == binding.user_id).first()
        if user and user.is_active:
            return {"access_token": auth_lib.create_access_token(user.username)}

    # openid 派生一个内部用户名（不直接暴露 openid）
    username = "wx_" + hashlib.sha256(openid.encode("utf-8")).hexdigest()[:16]
    exist_user = db.query(models.User).filter(models.User.username == username).first()
    if exist_user:
        # 有账号但绑定丢失（极端情况）：补回绑定而不是新建
        if not binding:
            db.add(models.WxBinding(user_id=exist_user.id, openid=openid))
            db.commit()
        return {"access_token": auth_lib.create_access_token(exist_user.username)}

    # 手机号选填，但填了就必须合法（前端已校验，后端不信任前端输入）
    phone = (data.phone or "").strip()
    if phone and not _phone_ok(phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    name = (data.name or "").strip() or ("会员" + openid[-4:])
    client = models.Client(name=name, phone=crypto_service.encrypt_phone(phone))
    db.add(client)
    db.flush()
    user = models.User(username=username,
                       password_hash=auth_lib.hash_password(_random_password()),
                       role="client", name=name, client_id=client.id)
    db.add(user)
    db.flush()
    if not binding:
        db.add(models.WxBinding(user_id=user.id, openid=openid))
    db.commit()
    db.refresh(user)
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

@router.post("/register", response_model=schemas.UserOut)
def register_client(data: ClientRegisterIn, db: Session = Depends(get_db)):
    """小程序客户自助注册；只创建 client 角色，不创建工作人员账号。"""
    if len(data.username.strip()) < 3 or len(data.password) < 6 or not data.name.strip():
        raise HTTPException(status_code=400, detail="请填写有效姓名、用户名（至少3位）和密码（至少6位）")
    if db.query(models.User).filter(models.User.username == data.username.strip()).first():
        raise HTTPException(status_code=409, detail="用户名已存在，请换一个")
    client = models.Client(name=data.name.strip())
    db.add(client)
    db.flush()
    user = models.User(username=data.username.strip(), password_hash=auth_lib.hash_password(data.password), role="client", name=data.name.strip(), client_id=client.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/phone-register", response_model=schemas.Token)
def phone_register(data: PhoneRegisterIn, db: Session = Depends(get_db)):
    """手机号快捷注册/登录：同一手机号一个客户档案，重复调用即登录已存在账号。

    前端调 wx.getPhoneNumber 拿 code（mock 模式下也可直接传 mock:手机号），
    后端换取手机号后：
      - 该手机号已注册 → 直接签发 token（等同于登录）
      - 未注册 → 新建客户档案 + 账号，用户名即手机号，并签发 token
    用户全程无需记用户名密码，符合主流小程序"授权即注册"的体验。
    返回 {access_token, user}，前端拿到即可直接进首页。
    """
    phone = _get_phone_by_code(data.wx_code or data.code)
    if not _phone_ok(phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    enc = crypto_service.encrypt_phone(phone)
    exist = db.query(models.Client).filter(models.Client.phone == enc).first()
    if exist:
        user = (db.query(models.User)
                .filter(models.User.client_id == exist.id,
                        models.User.role == "client").first())
        if not user:
            raise HTTPException(status_code=409, detail="该手机号已存在档案，请联系馆主")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="账号已注销，请联系馆主")
        return {"access_token": auth_lib.create_access_token(user.username)}

    if db.query(models.User).filter(models.User.username == phone).first():
        raise HTTPException(status_code=409, detail="该手机号已有账号，请直接登录")
    name = (data.name or "").strip() or ("会员" + phone[-4:])
    client = models.Client(name=name, phone=enc)
    db.add(client)
    db.flush()
    user = models.User(username=phone, password_hash=auth_lib.hash_password(_random_password()),
                       role="client", name=name, client_id=client.id)
    db.add(user)
    db.flush()

    # 顺带绑定微信（前端传了 wx.login 的 code），实现下次免密登录
    if data.wx_code:
        try:
            if settings.WX_DEV_MOCK and data.wx_code.startswith("mock:"):
                openid = "mock_openid_" + data.wx_code[5:]
            else:
                openid = _code2session(data.wx_code)
            if openid and not (db.query(models.WxBinding)
                               .filter(models.WxBinding.openid == openid).first()):
                db.add(models.WxBinding(user_id=user.id, openid=openid))
        except HTTPException:
            pass  # 绑定失败不影响注册成功
    db.commit()
    db.refresh(user)
    return {"access_token": auth_lib.create_access_token(user.username)}


def _random_password() -> str:
    """生成随机密码（用户不感知，仅用于满足账号唯一性）。"""
    import secrets
    return secrets.token_urlsafe(24)


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
