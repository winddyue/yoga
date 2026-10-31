# -*- coding: utf-8 -*-
"""微信支付：商品 / 订单 / JSAPI 下单 / 支付回调 / 退款。

场景：C 端学员付钱给瑜伽馆（如 399 团购卡），用馆主的商户号
（商户平台把小程序 AppID 绑定到商户号）。
未配置微信支付时相关接口返回 503，不静默降级。

幂等设计：
- 下单：同一客户同一商品存在未过期（100 分钟内）的 pending 订单则复用，
  只重新生成调起签名（prepay_id 2 小时有效）；
- 回调：订单已 paid 直接回 SUCCESS，不重复通知；
- 退款：out_refund_no 由商户订单号派生，微信端天然幂等。
"""
import datetime
import random

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db
from ..services import notify as notify_svc
from ..services import wxpay

router = APIRouter(prefix="/api", tags=["支付"])

# prepay_id 有效期 2 小时；复用窗口取 100 分钟，留余量
REUSE_WINDOW_MIN = 100

# 默认商品：随应用启动幂等预置（create_all 建表路径下 alembic 种子不执行，
# 这里保证新库/测试库也有商品；老库走 alembic 0004 种子）
DEFAULT_PRODUCTS = [
    {"name": "双十一399团购卡", "price_cents": 39900,
     "description": "身体评估私教×1 + 器械私教×1 + 普拉提小班两周 + 瑜伽团课14天；5人成团、团长免单"},
]


def ensure_default_products(db: Session) -> None:
    """幂等预置默认商品（同名 active 商品已存在则跳过）。"""
    for p in DEFAULT_PRODUCTS:
        exists = (db.query(models.Product)
                  .filter(models.Product.name == p["name"],
                          models.Product.active == True).first())  # noqa: E712
        if not exists:
            db.add(models.Product(name=p["name"], price_cents=p["price_cents"],
                                  description=p["description"], active=True))
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


@router.get("/products", response_model=list[schemas.ProductOut])
def list_products(db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.get_current_user)):
    """在售商品列表（登录即可；不调微信接口，无需支付配置）。"""
    return (db.query(models.Product)
            .filter(models.Product.active == True)  # noqa: E712
            .order_by(models.Product.id).all())  # noqa: E712


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

    cutoff = datetime.datetime.now() - datetime.timedelta(minutes=REUSE_WINDOW_MIN)
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
        order.paid_at = datetime.datetime.now()
        db.commit()
        _order_paid_notify(db, order)
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
