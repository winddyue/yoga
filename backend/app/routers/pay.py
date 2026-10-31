# -*- coding: utf-8 -*-
"""微信支付：商品 / 订单 / JSAPI 下单 / 支付回调 / 退款 + AI 会员订阅。

场景：学员付订阅费给瑜伽馆（馆主商户号）解锁 AI 功能。
支付回调驱动 ClientSubscription 创建/续期（见 _activate_subscription）。
商品（套餐价格/时长/上下架）由馆主通过 POST/PATCH /api/products 管理。
未配置微信支付时相关接口返回 503，不静默降级。

幂等设计：
- 下单：同一客户同一商品存在未过期（100 分钟内）的 pending 订单则复用，
  只重新生成调起签名（prepay_id 2 小时有效）；
- 回调：订单已 paid 直接回 SUCCESS，不重复通知；订阅激活同样幂等；
- 退款：out_refund_no 由商户订单号派生，微信端天然幂等。
"""
import datetime
import random

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session


def _utcnow() -> datetime.datetime:
    """UTC wall time（naive），与 models._now() 的入库基准一致。

    注意：绝不能用 naive 的 datetime.now()（本地时区）去和
    created_at/expires_at 等入库时间比较，否则会有 8 小时偏差。
    """
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db
from ..services import notify as notify_svc
from ..services import wxpay

router = APIRouter(prefix="/api", tags=["支付"])

# prepay_id 有效期 2 小时；复用窗口取 100 分钟，留余量
REUSE_WINDOW_MIN = 100

# 默认商品：随应用启动幂等预置（create_all 建表路径下 alembic 种子不执行，
# 这里保证新库/测试库也有商品；老库走 alembic 0005 种子）。
# 价格/时长为初始占位值，馆主可通过 PATCH /api/products/{id} 修改。
DEFAULT_PRODUCTS = [
    {"name": "AI 会员月卡", "price_cents": 2900, "kind": "subscription",
     "duration_days": 30,
     "description": "AI 功能 30 天使用权：AI 生成训练计划、AI 生成饮食方案"},
    {"name": "AI 会员季卡", "price_cents": 7900, "kind": "subscription",
     "duration_days": 90,
     "description": "AI 功能 90 天使用权：AI 生成训练计划、AI 生成饮食方案"},
    {"name": "AI 会员年卡", "price_cents": 29900, "kind": "subscription",
     "duration_days": 365,
     "description": "AI 功能 365 天使用权：AI 生成训练计划、AI 生成饮食方案"},
]


def ensure_default_products(db: Session) -> None:
    """幂等预置默认商品（同名 active 商品已存在则跳过）。"""
    for p in DEFAULT_PRODUCTS:
        exists = (db.query(models.Product)
                  .filter(models.Product.name == p["name"],
                          models.Product.active == True).first())  # noqa: E712
        if not exists:
            db.add(models.Product(name=p["name"], price_cents=p["price_cents"],
                                  description=p["description"],
                                  kind=p["kind"],
                                  duration_days=p["duration_days"],
                                  active=True))
    db.commit()


def _need_pay() -> None:
    if not wxpay.is_configured():
        raise HTTPException(status_code=503, detail="馆主尚未配置微信支付")


def _out_trade_no() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    return f"YG{ts}{random.randint(100000, 999999)}"


def _payer_openid(db: Session, user: models.User) -> str:
    b = (db.query(models.WxBinding)
         .filter(models.WxBinding.user_id == user.id).first())
    if not b:
        raise HTTPException(status_code=400, detail="请先用微信登录绑定后再支付")
    return b.openid


def _order_paid_notify(db: Session, order: models.Order) -> None:
    notify_svc.notify_client(
        db, order.client_id, "order_paid", "订单支付成功",
        f"{order.amount_cents / 100:.2f} 元已支付，欢迎到店使用。",
        ref_type="order", ref_id=order.id)


def _activate_subscription(db: Session, order: models.Order,
                           product: models.Product) -> None:
    """支付成功后开通/续期学员 AI 会员订阅（幂等）。

    expires_at = max(now, 当前有效期) + duration_days。
    过期记录顺手标 expired；同一客户只保留一条 active 记录。
    """
    days = product.duration_days or 0
    if days <= 0:
        return
    now = _utcnow()
    subs = (db.query(models.ClientSubscription)
            .filter(models.ClientSubscription.client_id == order.client_id)
            .order_by(models.ClientSubscription.expires_at.desc()).all())
    current = next((s for s in subs
                    if s.status == "active" and s.expires_at and s.expires_at > now),
                   None)
    base = current.expires_at if current else now
    new_exp = base + datetime.timedelta(days=days)
    for s in subs:
        if s is not current and s.status == "active":
            s.status = "expired"
    if current:
        current.expires_at = new_exp
        current.order_id = order.id
        current.product_id = product.id
    else:
        db.add(models.ClientSubscription(
            client_id=order.client_id, product_id=product.id,
            order_id=order.id, started_at=now,
            expires_at=new_exp, status="active"))
    db.commit()


@router.get("/products", response_model=list[schemas.ProductOut])
def list_products(all: bool = False,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.get_current_user)):
    """在售商品列表（登录即可；不调微信接口，无需支付配置）。
    ?all=true 时返回含已下架的全部套餐，仅 owner 可用（供订阅套餐管理页）。"""
    q = db.query(models.Product)
    if all:
        if user.role != "owner":
            raise HTTPException(status_code=403, detail="仅馆主可操作")
    else:
        q = q.filter(models.Product.active == True)  # noqa: E712
    return q.order_by(models.Product.id).all()


@router.post("/orders")
def create_order(data: schemas.OrderCreateIn,
                 db: Session = Depends(get_db),
                 user: models.User = Depends(auth_lib.get_current_user)):
    """创建订单并调微信 JSAPI 统一下单。

    仅客户账号（为自己下单）。返回小程序 wx.requestPayment 所需参数。
    """
    _need_pay()
    client = auth_lib.get_own_client(db, user)
    product = (db.query(models.Product)
               .filter(models.Product.id == data.product_id,
                       models.Product.active == True).first())  # noqa: E712
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    openid = _payer_openid(db, user)

    cutoff = _utcnow() - datetime.timedelta(minutes=REUSE_WINDOW_MIN)
    order = (db.query(models.Order)
             .filter(models.Order.client_id == client.id,
                     models.Order.product_id == product.id,
                     models.Order.status == "pending",
                     models.Order.created_at >= cutoff)
             .order_by(models.Order.id.desc()).first())
    if order is None:
        order = models.Order(out_trade_no=_out_trade_no(), client_id=client.id,
                             product_id=product.id,
                             amount_cents=product.price_cents)
        db.add(order)
        db.commit()
        db.refresh(order)

    if not order.prepay_id:
        # 统一下单（复用订单时 prepay_id 仍有效，只需重新生成调起签名）
        try:
            order.prepay_id = wxpay.jsapi_unified_order(
                description=product.name, out_trade_no=order.out_trade_no,
                amount_cents=order.amount_cents, openid=openid)
        except wxpay.WxPayError as e:
            db.commit()
            raise HTTPException(status_code=502, detail=f"微信下单失败：{e}")
        db.commit()
        db.refresh(order)

    try:
        params = wxpay.build_prepay_params(order.prepay_id)
    except wxpay.WxPayError as e:
        raise HTTPException(status_code=502, detail=f"支付签名失败：{e}")
    return {"order_id": order.id, "out_trade_no": order.out_trade_no,
            "prepay_params": params}


@router.post("/pay/notify")
async def pay_notify(request: Request, db: Session = Depends(get_db)):
    """微信支付回调：验签 → 解密 → 幂等更新订单 → 通知客户。

    无需登录态（微信服务端调用）。验签失败 400；未知订单仍回 SUCCESS
    避免微信重试风暴。
    """
    body = (await request.body()).decode("utf-8")
    try:
        txn = wxpay.parse_notify(dict(request.headers), body)
    except wxpay.WxPayError as e:
        raise HTTPException(status_code=400, detail=f"回调验签失败：{e}")

    order = (db.query(models.Order)
             .filter(models.Order.out_trade_no == txn.get("out_trade_no"))
             .first())
    if order is None:
        return {"code": "SUCCESS", "message": "OK"}
    if order.status == "paid":
        return {"code": "SUCCESS", "message": "OK"}  # 幂等：重复回调
    if txn.get("trade_state") == "SUCCESS":
        order.status = "paid"
        order.transaction_id = txn.get("transaction_id", "")
        order.paid_at = _utcnow()
        db.commit()
        _order_paid_notify(db, order)
        # 订阅类商品：自动开通/续期学员 AI 会员
        product = (db.query(models.Product)
                   .filter(models.Product.id == order.product_id).first())
        if product and product.kind == "subscription":
            _activate_subscription(db, order, product)
    return {"code": "SUCCESS", "message": "OK"}


@router.post("/orders/{order_id}/refund")
def refund_order(order_id: int,
                 db: Session = Depends(get_db),
                 user: models.User = Depends(auth_lib.require_owner)):
    """仅馆主：微信退款（全额原路退回）。"""
    _need_pay()
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != "paid":
        raise HTTPException(status_code=400, detail="仅已支付订单可退款")
    # out_refund_no 由商户订单号派生：重复退款请求微信端幂等
    out_refund_no = f"RF{order.out_trade_no}"
    try:
        wxpay.refund(out_trade_no=order.out_trade_no,
                     out_refund_no=out_refund_no,
                     total_cents=order.amount_cents,
                     refund_cents=order.amount_cents)
    except wxpay.WxPayError as e:
        raise HTTPException(status_code=502, detail=f"微信退款失败：{e}")
    order.status = "refunded"
    db.commit()
    notify_svc.notify_client(
        db, order.client_id, "order_refunded", "订单已退款",
        f"{order.amount_cents / 100:.2f} 元将原路退回，请注意查收。",
        ref_type="order", ref_id=order.id)
    return {"ok": True}


@router.get("/orders/mine", response_model=list[schemas.OrderOut])
def my_orders(db: Session = Depends(get_db),
              user: models.User = Depends(auth_lib.get_current_user)):
    """当前客户的订单。"""
    client = auth_lib.get_own_client(db, user)
    return (db.query(models.Order)
            .filter(models.Order.client_id == client.id)
            .order_by(models.Order.id.desc()).all())


@router.get("/orders", response_model=list[schemas.OrderOut])
def all_orders(db: Session = Depends(get_db),
               user: models.User = Depends(auth_lib.require_staff),
               client_id: int | None = Query(default=None)):
    """工作人员看全馆订单；可按 ?client_id= 过滤（走 client_visible_to）。"""
    q = db.query(models.Order)
    if client_id:
        auth_lib.client_visible_to(db, user, client_id)
        q = q.filter(models.Order.client_id == client_id)
    return q.order_by(models.Order.id.desc()).limit(200).all()


@router.get("/subscriptions/mine")
def my_subscription(db: Session = Depends(get_db),
                    user: models.User = Depends(auth_lib.get_current_user)):
    """当前客户的 AI 会员订阅状态。"""
    from ..services import ai_gate
    client = auth_lib.get_own_client(db, user)
    sub = ai_gate.active_client_subscription(db, client.id)
    if not sub:
        return {"active": False, "plan_name": None, "expires_at": None}
    product = (db.query(models.Product)
               .filter(models.Product.id == sub.product_id).first())
    return {"active": True,
            "plan_name": product.name if product else "",
            "expires_at": sub.expires_at.isoformat(sep=" ", timespec="seconds")
            if sub.expires_at else None}


@router.post("/products", response_model=schemas.ProductOut)
def create_product(data: schemas.ProductCreateIn,
                   db: Session = Depends(get_db),
                   user: models.User = Depends(auth_lib.require_owner)):
    """新建订阅套餐（仅馆主）：名称/价格/时长/描述。"""
    product = models.Product(
        name=data.name, price_cents=data.price_cents,
        description=data.description or "",
        kind=data.kind or "subscription",
        duration_days=data.duration_days or 0,
        active=True)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/products/{product_id}", response_model=schemas.ProductOut)
def update_product(product_id: int, data: schemas.ProductUpdateIn,
                   db: Session = Depends(get_db),
                   user: models.User = Depends(auth_lib.require_owner)):
    """修改套餐（仅馆主）：改价/改时长/改描述/上下架。

    已售出订单不受影响（Order.amount_cents 是下单时快照）；
    新订单按下单时的商品现价。
    """
    product = (db.query(models.Product)
               .filter(models.Product.id == product_id).first())
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    for field in ("name", "price_cents", "description", "kind",
                  "duration_days", "active"):
        value = getattr(data, field)
        if value is not None:
            if field == "price_cents" and value < 0:
                raise HTTPException(status_code=400, detail="价格不能为负")
            if field == "duration_days" and value < 0:
                raise HTTPException(status_code=400, detail="时长不能为负")
            setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product
