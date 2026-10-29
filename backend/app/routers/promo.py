# -*- coding: utf-8 -*-
"""拓客裂变（MVP）：微信网页授权 OAuth、专属分享链接、报名、拼团、后台看板。

链路（对标 51maiju/助力美）：
  展示页 --点击--> /oauth/url 取微信授权地址 --> 微信 OAuth -->
  /oauth/callback（换 openid、建档、记录推荐归因、签发 promo token）-->
  前端拿 token 调 /share-link 生成专属链接 --> 转发 -->
  好友打开带 ref 参数的链接 --> /share/verify 验签并展示推荐人 -->
  好友同样 OAuth 后归因到推荐人名下 --> /signup 报名（可拼团）。

配置：WX_MP_APPID / WX_MP_SECRET（公众号网页授权，与小程序不是同一应用）、
PROMO_FRONT_URL（活动页前端地址）、PUBLIC_API_URL（本接口的公网地址，
用于拼 OAuth redirect_uri）。本地联调：WX_DEV_MOCK=true 时 code 用
"mock:任意标识" 即可走通全流程，不依赖真实微信。
"""
import hashlib
import hmac
import re
import secrets
import urllib.parse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models
from ..config import settings
from ..database import get_db
from ..services import crypto as crypto_service

router = APIRouter(prefix="/api/promo", tags=["拓客裂变"])

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
OAUTH_AUTHORIZE = "https://open.weixin.qq.com/connect/oauth2/authorize"


# ---------- 内部工具 ----------

def _require_mp_config():
    """公众号未配置时给出可操作的提示，而不是笼统报错。"""
    if not settings.WX_MP_APPID or not settings.WX_MP_SECRET:
        raise HTTPException(
            status_code=400,
            detail="未配置微信公众号 AppID/Secret：请在公众号后台完成认证并配置网页授权域名，"
                   "然后设置环境变量 WX_MP_APPID / WX_MP_SECRET",
        )
    if not settings.PUBLIC_API_URL:
        raise HTTPException(
            status_code=400,
            detail="未配置 PUBLIC_API_URL：请设置为本接口的公网地址（如 https://api.zytzml.cn），"
                   "用于拼接微信 OAuth 回调地址",
        )


def _callback_url() -> str:
    return settings.PUBLIC_API_URL.rstrip("/") + "/api/promo/oauth/callback"


def _sign_ref(activity_id: int, ref_code: str) -> str:
    """分享链接防伪签名（对标 51maiju 的 sec 参数），防伪造推荐关系。"""
    msg = f"{activity_id}:{ref_code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:16]


def _promo_token(openid: str) -> str:
    return auth_lib.create_access_token("promo:" + openid)


def get_current_promo_user(
    db: Session = Depends(get_db),
    token: str = Depends(auth_lib.oauth2_scheme),
) -> models.PromoUser:
    """从 promo token 解析当前拓客用户；无效则 401。"""
    exc = HTTPException(status_code=401, detail="登录已过期，请重新授权")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        sub = payload.get("sub") or ""
    except JWTError:
        raise exc
    if not sub.startswith("promo:"):
        raise exc
    user = db.query(models.PromoUser).filter(
        models.PromoUser.openid == sub[len("promo:"):]).first()
    if not user:
        raise exc
    return user


def _get_or_create_share(db: Session, activity_id: int, user_id: int) -> models.PromoShare:
    share = db.query(models.PromoShare).filter(
        models.PromoShare.activity_id == activity_id,
        models.PromoShare.user_id == user_id).first()
    if not share:
        share = models.PromoShare(
            activity_id=activity_id, user_id=user_id,
            ref_code=secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12],
        )
        db.add(share)
        db.commit()
        db.refresh(share)
    return share


def _share_url(activity_id: int, ref_code: str) -> str:
    sig = _sign_ref(activity_id, ref_code)
    base = settings.PROMO_FRONT_URL.rstrip("/") if settings.PROMO_FRONT_URL else ""
    return f"{base}/?activity={activity_id}&ref={ref_code}&sig={sig}"


def _exchange_code(code: str) -> tuple[str, str, str]:
    """code -> (openid, nickname, avatar)。mock 模式直接返回模拟身份。"""
    if settings.WX_DEV_MOCK and code.startswith("mock:"):
        ident = code[len("mock:"):]
        return "mockmp_" + ident, "微信用户" + ident[-4:], ""
    if code.startswith("mock:"):
        raise HTTPException(status_code=400,
                            detail="后端未开启 WX_DEV_MOCK，无法使用 mock: code 联调")
    _require_mp_config()
    try:
        r = httpx.get(
            "https://api.weixin.qq.com/sns/oauth2/access_token",
            params={"appid": settings.WX_MP_APPID, "secret": settings.WX_MP_SECRET,
                    "code": code, "grant_type": "authorization_code"},
            timeout=10,
        )
        data = r.json()
    except Exception:
        raise HTTPException(status_code=502, detail="请求微信接口失败，请稍后重试")
    openid = data.get("openid")
    if not openid:
        raise HTTPException(status_code=400,
                            detail=f"微信授权失败：{data.get('errmsg', '未知错误')}")
    nickname, avatar = "", ""
    try:
        u = httpx.get(
            "https://api.weixin.qq.com/sns/userinfo",
            params={"access_token": data["access_token"], "openid": openid, "lang": "zh_CN"},
            timeout=10,
        ).json()
        nickname, avatar = u.get("nickname", ""), u.get("headimgurl", "")
    except Exception:
        pass
    return openid, nickname, avatar


# ---------- OAuth ----------

@router.get("/oauth/url")
def oauth_url(activity_id: int = Query(...), ref: str = Query(default="")):
    """拼出微信网页授权地址。state 携带 activity_id 和推荐码 ref。"""
    _require_mp_config()
    state = f"{activity_id}:{ref}" if ref else str(activity_id)
    params = {
        "appid": settings.WX_MP_APPID,
        "redirect_uri": _callback_url(),
        "response_type": "code",
        "scope": "snsapi_userinfo",
        "state": state,
    }
    url = OAUTH_AUTHORIZE + "?" + urllib.parse.urlencode(params) + "#wechat_redirect"
    return {"url": url}


@router.get("/oauth/callback")
def oauth_callback(code: str = Query(...), state: str = Query(default=""),
                   db: Session = Depends(get_db)):
    """微信 OAuth 回调：换 openid、建档、记录推荐归因、签发 promo token。"""
    openid, nickname, avatar = _exchange_code(code)
    user = db.query(models.PromoUser).filter(models.PromoUser.openid == openid).first()
    if not user:
        user = models.PromoUser(openid=openid, nickname=nickname, avatar_url=avatar)
        db.add(user)
        db.commit()
        db.refresh(user)

    activity_id, ref_code = None, ""
    if state:
        parts = state.split(":", 1)
        if parts[0].isdigit():
            activity_id = int(parts[0])
        if len(parts) > 1:
            ref_code = parts[1]

    referrer = None
    if activity_id and ref_code:
        share = db.query(models.PromoShare).filter(
            models.PromoShare.activity_id == activity_id,
            models.PromoShare.ref_code == ref_code).first()
        if share and share.user_id != user.id:
            referrer = db.query(models.PromoUser).filter(
                models.PromoUser.id == share.user_id).first()
            # 记录一次归因访问（同一人多次进入只记首次，避免刷量）
            existed = db.query(models.PromoVisit).filter(
                models.PromoVisit.activity_id == activity_id,
                models.PromoVisit.visitor_id == user.id).first()
            if not existed:
                db.add(models.PromoVisit(
                    activity_id=activity_id, share_id=share.id,
                    referrer_id=share.user_id, visitor_id=user.id))
                share.visit_count += 1
                db.commit()

    share_info = None
    if activity_id:
        share = _get_or_create_share(db, activity_id, user.id)
        share_info = {"ref_code": share.ref_code, "url": _share_url(activity_id, share.ref_code)}

    token = _promo_token(openid)
    # 生产环境：回调后跳回活动页（静态页从 URL 读 token 继续报名/分享流程）。
    # PROMO_FRONT_URL 未配置时（如本地 mock 联调）保持返回 JSON，测试不受影响。
    if settings.PROMO_FRONT_URL:
        params = {
            "activity": activity_id or "",
            "promo_token": token,
            "nickname": user.nickname,
            "ref_code": share_info["ref_code"] if share_info else "",
            "referrer": referrer.nickname if referrer else "",
        }
        landing = settings.PROMO_FRONT_URL.rstrip("/") + "/?" + urllib.parse.urlencode(params)
        return RedirectResponse(landing, status_code=302)

    return {
        "token": token,
        "openid": openid,
        "nickname": user.nickname,
        "activity_id": activity_id,
        "referrer": {"id": referrer.id, "nickname": referrer.nickname} if referrer else None,
        "share": share_info,
    }


# ---------- 分享链接 ----------

@router.get("/share-link")
def share_link(activity_id: int = Query(...),
               user: models.PromoUser = Depends(get_current_promo_user),
               db: Session = Depends(get_db)):
    """获取我的专属分享链接（带防伪签名）。"""
    act = db.query(models.PromoActivity).filter(
        models.PromoActivity.id == activity_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    share = _get_or_create_share(db, activity_id, user.id)
    return {"ref_code": share.ref_code, "url": _share_url(activity_id, share.ref_code),
            "visit_count": share.visit_count, "signup_count": share.signup_count}


@router.get("/share/verify")
def share_verify(activity_id: int = Query(...), ref: str = Query(...),
                 sig: str = Query(...), db: Session = Depends(get_db)):
    """打开分享链接时验签：确认推荐人身份真实有效（防伪造）。"""
    if not hmac.compare_digest(_sign_ref(activity_id, ref), sig or ""):
        return {"valid": False, "reason": "签名无效"}
    share = db.query(models.PromoShare).filter(
        models.PromoShare.activity_id == activity_id,
        models.PromoShare.ref_code == ref).first()
    if not share:
        return {"valid": False, "reason": "分享链接不存在"}
    sharer = db.query(models.PromoUser).filter(
        models.PromoUser.id == share.user_id).first()
    return {"valid": True, "sharer": {"id": sharer.id, "nickname": sharer.nickname,
                                     "avatar_url": sharer.avatar_url}}


# ---------- 报名与拼团 ----------

class SignupIn(BaseModel):
    activity_id: int
    name: str
    phone: str
    ref: str = ""  # 推荐码（可空，OAuth 时已归因则可不传）


@router.post("/signup")
def signup(body: SignupIn, user: models.PromoUser = Depends(get_current_promo_user),
           db: Session = Depends(get_db)):
    """活动报名：校验手机号、加密存储、归因推荐人、自动拼团。"""
    act = db.query(models.PromoActivity).filter(
        models.PromoActivity.id == body.activity_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    if act.status != "active":
        raise HTTPException(status_code=400, detail="活动未开始或已结束")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="请填写姓名")
    if not PHONE_RE.match(body.phone.strip()):
        raise HTTPException(status_code=400, detail="手机号格式不正确")

    existed = db.query(models.PromoSignup).filter(
        models.PromoSignup.activity_id == act.id,
        models.PromoSignup.user_id == user.id).first()
    if existed and existed.status != "cancelled":
        raise HTTPException(status_code=400, detail="您已报名，请勿重复提交")

    referrer_id = None
    if body.ref:
        share = db.query(models.PromoShare).filter(
            models.PromoShare.activity_id == act.id,
            models.PromoShare.ref_code == body.ref).first()
        if share and share.user_id != user.id:
            referrer_id = share.user_id
    if referrer_id is None:
        # OAuth 时已记录的归因访问同样生效
        visit = db.query(models.PromoVisit).filter(
            models.PromoVisit.activity_id == act.id,
            models.PromoVisit.visitor_id == user.id).first()
        if visit and visit.referrer_id != user.id:
            referrer_id = visit.referrer_id
    if referrer_id is not None:
        # 推荐人带来一次有效报名：计数 +1（无论推荐码是链接里带的还是 OAuth 归因的）
        rshare = db.query(models.PromoShare).filter(
            models.PromoShare.activity_id == act.id,
            models.PromoShare.user_id == referrer_id).first()
        if rshare:
            rshare.signup_count += 1

    if existed:  # 曾取消，重新报名
        signup = existed
        signup.name = name
        signup.phone_enc = crypto_service.encrypt_phone(body.phone.strip())
        signup.status = "pending"
        signup.referrer_id = referrer_id
    else:
        signup = models.PromoSignup(
            activity_id=act.id, user_id=user.id, name=name,
            phone_enc=crypto_service.encrypt_phone(body.phone.strip()),
            referrer_id=referrer_id)
        db.add(signup)
    db.flush()

    group_info = None
    if act.group_size and act.group_size > 1:
        group_info = _join_group(db, act, user, referrer_id, signup)
    db.commit()
    db.refresh(signup)
    return {"signup_id": signup.id, "status": signup.status, "group": group_info}


def _join_group(db: Session, act: models.PromoActivity, user: models.PromoUser,
                referrer_id: int | None, signup: models.PromoSignup) -> dict:
    """拼团：优先加入推荐人的团，否则加入任一未满的团，否则自己开团。"""
    group = None
    if referrer_id:
        group = db.query(models.PromoGroup).filter(
            models.PromoGroup.activity_id == act.id,
            models.PromoGroup.leader_id == referrer_id,
            models.PromoGroup.status == "forming").first()
    if not group:
        # 找成员未满的团
        forming = db.query(models.PromoGroup).filter(
            models.PromoGroup.activity_id == act.id,
            models.PromoGroup.status == "forming").all()
        for g in forming:
            n = db.query(models.PromoSignup).filter(
                models.PromoSignup.group_id == g.id,
                models.PromoSignup.status != "cancelled").count()
            if n < act.group_size:
                group = g
                break
    if not group:
        group = models.PromoGroup(activity_id=act.id, leader_id=user.id)
        db.add(group)
        db.flush()
    signup.group_id = group.id
    db.flush()
    members = db.query(models.PromoSignup).filter(
        models.PromoSignup.group_id == group.id,
        models.PromoSignup.status != "cancelled").count()
    if members >= act.group_size:
        group.status = "full"
    return {"group_id": group.id, "status": group.status,
            "members": members, "needed": act.group_size}


@router.get("/my-group")
def my_group(activity_id: int = Query(...),
             user: models.PromoUser = Depends(get_current_promo_user),
             db: Session = Depends(get_db)):
    """我的拼团状态：成员数、还差几人、是否成团。"""
    act = db.query(models.PromoActivity).filter(
        models.PromoActivity.id == activity_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="活动不存在")
    signup = db.query(models.PromoSignup).filter(
        models.PromoSignup.activity_id == activity_id,
        models.PromoSignup.user_id == user.id,
        models.PromoSignup.status != "cancelled").first()
    if not signup or not signup.group_id:
        return {"in_group": False}
    members = db.query(models.PromoSignup, models.PromoUser).join(
        models.PromoUser, models.PromoSignup.user_id == models.PromoUser.id).filter(
        models.PromoSignup.group_id == signup.group_id,
        models.PromoSignup.status != "cancelled").all()
    group = db.query(models.PromoGroup).filter(
        models.PromoGroup.id == signup.group_id).first()
    return {
        "in_group": True, "group_id": group.id, "status": group.status,
        "needed": act.group_size,
        "members": [{"nickname": m[1].nickname, "name": m[0].name} for m in members],
    }


# ---------- 后台看板（仅馆主） ----------

class ActivityIn(BaseModel):
    title: str
    start_at: str = ""
    end_at: str = ""
    group_size: int = 0
    rules: str = ""
    status: str = "draft"


@router.post("/admin/activities")
def admin_create_activity(body: ActivityIn, db: Session = Depends(get_db),
                          _owner=Depends(auth_lib.require_owner)):
    act = models.PromoActivity(title=body.title.strip(), status=body.status,
                               start_at=body.start_at, end_at=body.end_at,
                               group_size=max(0, body.group_size), rules=body.rules,
                               created_by=_owner.id)
    if not act.title:
        raise HTTPException(status_code=400, detail="请填写活动标题")
    db.add(act)
    db.commit()
    db.refresh(act)
    return {"id": act.id, "title": act.title, "status": act.status}


@router.get("/admin/activities")
def admin_list_activities(db: Session = Depends(get_db),
                          _owner=Depends(auth_lib.require_owner)):
    acts = db.query(models.PromoActivity).order_by(
        models.PromoActivity.id.desc()).all()
    out = []
    for a in acts:
        visits = db.query(models.PromoVisit).filter(
            models.PromoVisit.activity_id == a.id).count()
        signups = db.query(models.PromoSignup).filter(
            models.PromoSignup.activity_id == a.id,
            models.PromoSignup.status != "cancelled").count()
        out.append({"id": a.id, "title": a.title, "status": a.status,
                    "start_at": a.start_at, "end_at": a.end_at,
                    "group_size": a.group_size, "visits": visits, "signups": signups})
    return out


@router.get("/admin/signups")
def admin_list_signups(activity_id: int = Query(...), db: Session = Depends(get_db),
                       _owner=Depends(auth_lib.require_owner)):
    rows = db.query(models.PromoSignup, models.PromoUser).join(
        models.PromoUser, models.PromoSignup.user_id == models.PromoUser.id).filter(
        models.PromoSignup.activity_id == activity_id).order_by(
        models.PromoSignup.id.desc()).all()
    users = {u.id: u for _, u in rows}
    out = []
    for s, u in rows:
        ref = users.get(s.referrer_id)
        out.append({
            "id": s.id, "name": s.name,
            "phone": crypto_service.decrypt_phone(s.phone_enc),
            "nickname": u.nickname, "status": s.status,
            "group_id": s.group_id,
            "referrer": ref.nickname if ref else "",
            "created_at": s.created_at.isoformat() if s.created_at else "",
        })
    return out


@router.get("/admin/referrals")
def admin_referrals(activity_id: int = Query(...), db: Session = Depends(get_db),
                    _owner=Depends(auth_lib.require_owner)):
    """推荐关系看板：每人带来的访问数、报名数、下级名单。"""
    shares = db.query(models.PromoShare, models.PromoUser).join(
        models.PromoUser, models.PromoShare.user_id == models.PromoUser.id).filter(
        models.PromoShare.activity_id == activity_id).all()
    out = []
    for share, u in shares:
        children = db.query(models.PromoUser).join(
            models.PromoVisit,
            models.PromoVisit.visitor_id == models.PromoUser.id).filter(
            models.PromoVisit.activity_id == activity_id,
            models.PromoVisit.referrer_id == u.id).all()
        out.append({
            "user_id": u.id, "nickname": u.nickname,
            "ref_code": share.ref_code,
            "visits": share.visit_count, "signups": share.signup_count,
            "invited": [{"id": c.id, "nickname": c.nickname} for c in children],
        })
    out.sort(key=lambda x: x["signups"], reverse=True)
    return out


@router.post("/admin/signups/{signup_id}/verify")
def admin_verify_signup(signup_id: int, db: Session = Depends(get_db),
                        _owner=Depends(auth_lib.require_owner)):
    """核销：客户到店后确认，报名生效。"""
    s = db.query(models.PromoSignup).filter(
        models.PromoSignup.id == signup_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="报名不存在")
    s.status = "verified"
    db.commit()
    return {"id": s.id, "status": s.status}


@router.post("/admin/signups/{signup_id}/cancel")
def admin_cancel_signup(signup_id: int, db: Session = Depends(get_db),
                        _owner=Depends(auth_lib.require_owner)):
    s = db.query(models.PromoSignup).filter(
        models.PromoSignup.id == signup_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="报名不存在")
    s.status = "cancelled"
    db.commit()
    return {"id": s.id, "status": s.status}
