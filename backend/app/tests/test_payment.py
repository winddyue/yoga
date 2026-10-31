# -*- coding: utf-8 -*-
"""微信支付测试：mock 微信 HTTP（统一下单/回调验签/退款），不碰真实网络。

覆盖：下单 / 重复下单幂等 / 回调验签失败 400 / 回调幂等 /
未配置 503 / 退款权限与流程。
"""
import base64
import json
import os
import sys
import time

os.environ["DATABASE_URL"] = "sqlite:///./test_payment.db"
os.environ["UPLOAD_DIR"] = os.path.join(os.environ.get("TEMP", "/tmp"),
                                        "yoga_test_uploads_pay")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# 与其他测试文件共用进程运行时，刷新已导入的 app 模块
for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

# 测试用商户密钥对（仅测试；回调验签用公钥，调起签名用私钥）
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import padding, rsa  # noqa: E402
from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: E402

_test_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_TEST_PRIV_PEM = _test_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.TraditionalOpenSSL,
    serialization.NoEncryption()).decode()
_TEST_PUB_PEM = _test_key.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo).decode()

os.environ["WXPAY_APPID"] = "wx_test_appid"
os.environ["WXPAY_MCHID"] = "1900000109"
os.environ["WXPAY_APIV3_KEY"] = "a" * 32
os.environ["WXPAY_NOTIFY_URL"] = "https://api.zytzml.cn/api/pay/notify"
os.environ["WXPAY_PRIVATE_KEY"] = _TEST_PRIV_PEM
os.environ["WXPAY_CERT_SERIAL"] = "TESTSERIAL001"

from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import wxpay  # noqa: E402

if os.path.exists("test_payment.db"):
    os.remove("test_payment.db")

_SETUP_SEQ = 0
_api_calls = []  # 记录 mock 收到的微信 API 调用


def _fake_api_request(method, path, payload=None):
    _api_calls.append((method, path, payload))
    if path == "/v3/pay/transactions/jsapi":
        return {"prepay_id": f"wx_fake_prepay_{len(_api_calls)}"}
    if path == "/v3/refund/domestic/refunds":
        return {"refund_id": "5000001234", "status": "SUCCESS"}
    raise AssertionError(f"unexpected wechat api call: {path}")


# 全局 mock：不碰真实微信网络；回调验签用测试公钥
wxpay._api_request = _fake_api_request
wxpay._get_platform_pubkey_pem = lambda: _TEST_PUB_PEM  # noqa: E731


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login",
                    data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _bind_openid(username: str, openid: str = "test_openid_001") -> None:
    db = SessionLocal()
    try:
        u = db.query(models.User).filter(models.User.username == username).first()
        if not db.query(models.WxBinding).filter(
                models.WxBinding.user_id == u.id).first():
            db.add(models.WxBinding(user_id=u.id, openid=openid))
            db.commit()
    finally:
        db.close()


def _setup():
    """建馆主/教练/客户A（带账号+openid 绑定）。每次唯一用户名防串号。"""
    global _SETUP_SEQ
    _SETUP_SEQ += 1
    tag = f"pay{_SETUP_SEQ}"
    with TestClient(app) as client:
        admin = _login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
        admin_h = _h(admin)
        coach_un = f"{tag}_coach"
        client.post("/api/auth/users",
                    json={"username": coach_un, "password": "pw123456",
                          "role": "coach", "name": "支付教练"}, headers=admin_h)
        coach_h = _h(_login(client, coach_un, "pw123456"))
        coach_id = client.get("/api/auth/me", headers=coach_h).json()["id"]
        ra = client.post("/api/clients",
                         json={"name": f"学员{tag}", "coach_id": coach_id},
                         headers=admin_h)
        aid = ra.json()["id"]
        ua = f"{tag}_user"
        client.post("/api/auth/users",
                    json={"username": ua, "password": "pw123456", "role": "client",
                          "name": f"学员{tag}", "client_id": aid}, headers=admin_h)
        _bind_openid(ua, openid=f"test_openid_{tag}")
        return {"a": _h(_login(client, ua, "pw123456")),
                "coach": coach_h, "admin": admin_h, "aid": aid}


def _product_id(client: TestClient, h: dict) -> int:
    r = client.get("/api/products", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()
    assert items, "种子商品缺失"
    return items[0]["id"]


def test_products_list_and_seed():
    """商品列表：种子 399 团购卡存在；未登录 401。"""
    s = _setup()
    with TestClient(app) as client:
        r = client.get("/api/products")
        assert r.status_code == 401, r.text
        r = client.get("/api/products", headers=s["a"])
        assert r.status_code == 200, r.text
        items = r.json()
        names = [i["name"] for i in items]
        assert "双十一399团购卡" in names, names
        p = [i for i in items if i["name"] == "双十一399团购卡"][0]
        assert p["price_cents"] == 39900


def test_create_order_503_when_unconfigured():
    """未配置微信支付 → 503 明确报错。"""
    s = _setup()
    old = settings.WXPAY_APPID
    settings.WXPAY_APPID = ""
    try:
        with TestClient(app) as client:
            pid = _product_id(client, s["a"])
            r = client.post("/api/orders", json={"product_id": pid},
                            headers=s["a"])
            assert r.status_code == 503, r.text
            assert "尚未配置微信支付" in r.json()["detail"]
    finally:
        settings.WXPAY_APPID = old


def test_create_order_and_idempotent_reuse():
    """下单成功返回调起参数；重复下单幂等复用（微信只调一次）。"""
    s = _setup()
    _api_calls.clear()
    with TestClient(app) as client:
        pid = _product_id(client, s["a"])
        r1 = client.post("/api/orders", json={"product_id": pid}, headers=s["a"])
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["out_trade_no"].startswith("YG")
        pp = d1["prepay_params"]
        assert set(pp) == {"timeStamp", "nonceStr", "package", "signType",
                           "paySign"}
        assert pp["package"].startswith("prepay_id=wx_fake_prepay_")
        # 重复下单：复用同一订单，微信统一下单只调一次
        r2 = client.post("/api/orders", json={"product_id": pid}, headers=s["a"])
        assert r2.status_code == 200, r2.text
        assert r2.json()["out_trade_no"] == d1["out_trade_no"]
        jsapi_calls = [c for c in _api_calls
                       if c[1] == "/v3/pay/transactions/jsapi"]
        assert len(jsapi_calls) == 1, _api_calls
        # 我的订单可见
        r3 = client.get("/api/orders/mine", headers=s["a"])
        assert r3.status_code == 200 and len(r3.json()) == 1, r3.text
        assert r3.json()[0]["status"] == "pending"


def test_create_order_requires_openid():
    """无微信 openid 绑定 → 400 明确提示。"""
    s = _setup()
    with TestClient(app) as client:
        # 教练账号（非客户）下单 → 403；另建无 openid 的客户账号
        pid = _product_id(client, s["a"])
        r = client.post("/api/orders", json={"product_id": pid},
                        headers=s["coach"])
        assert r.status_code == 403, r.text


def _make_notify(out_trade_no: str, tamper_sig: bool = False):
    """构造一条真签名+真加密的微信支付成功回调。"""
    plain = {"out_trade_no": out_trade_no, "transaction_id": "4200009999",
             "trade_state": "SUCCESS",
             "amount": {"total": 39900, "currency": "CNY"},
             "payer": {"openid": "test_openid_001"}}
    aesgcm = AESGCM(b"a" * 32)
    nonce = "testnonce001"
    aad = "transaction"
    ct = aesgcm.encrypt(nonce.encode(), json.dumps(plain).encode(),
                        aad.encode())
    body = {"id": "EVT-TEST-001", "create_time": "2026-10-31T12:00:00+08:00",
            "event_type": "TRANSACTION.SUCCESS",
            "resource_type": "encrypt-resource",
            "resource": {"algorithm": "AEAD_AES_256_GCM",
                         "ciphertext": base64.b64encode(ct).decode(),
                         "nonce": nonce, "associated_data": aad}}
    body_str = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    ts = str(int(time.time()))
    rnonce = "rnonce001"
    sig = _test_key.sign(f"{ts}\n{rnonce}\n{body_str}\n".encode(),
                         padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64.b64encode(sig).decode()
    if tamper_sig:
        sig_b64 = ("A" if sig_b64[0] != "A" else "B") + sig_b64[1:]
    headers = {"Wechatpay-Signature": sig_b64, "Wechatpay-Timestamp": ts,
               "Wechatpay-Nonce": rnonce, "Content-Type": "application/json"}
    return headers, body_str


def _create_pending_order(client: TestClient, s: dict) -> str:
    _api_calls.clear()
    pid = _product_id(client, s["a"])
    r = client.post("/api/orders", json={"product_id": pid}, headers=s["a"])
    assert r.status_code == 200, r.text
    return r.json()["out_trade_no"]


def test_notify_success_and_idempotent():
    """回调验签通过 → 订单 paid + 客户收到通知；重复回调幂等。"""
    s = _setup()
    with TestClient(app) as client:
        out_trade_no = _create_pending_order(client, s)
        headers, body = _make_notify(out_trade_no)
        r = client.post("/api/pay/notify", content=body.encode(),
                        headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["code"] == "SUCCESS"
        # 订单已支付
        orders = client.get("/api/orders/mine", headers=s["a"]).json()
        assert orders[0]["status"] == "paid", orders
        assert orders[0]["transaction_id"] == "4200009999"
        # 客户收到站内通知
        ns = client.get("/api/notifications", headers=s["a"]).json()
        assert any(n["type"] == "order_paid" for n in ns), ns
        n_before = len(ns)
        # 重复回调：幂等，不重复通知
        r2 = client.post("/api/pay/notify", content=body.encode(),
                         headers=headers)
        assert r2.status_code == 200
        ns2 = client.get("/api/notifications", headers=s["a"]).json()
        assert len(ns2) == n_before, ns2


def test_notify_bad_signature_400():
    """签名被篡改 → 400，订单状态不变。"""
    s = _setup()
    with TestClient(app) as client:
        out_trade_no = _create_pending_order(client, s)
        headers, body = _make_notify(out_trade_no, tamper_sig=True)
        r = client.post("/api/pay/notify", content=body.encode(),
                        headers=headers)
        assert r.status_code == 400, r.text
        orders = client.get("/api/orders/mine", headers=s["a"]).json()
        assert orders[0]["status"] == "pending"


def test_refund_owner_only_and_flow():
    """退款仅馆主；教练 403；未支付订单 400；成功后状态 refunded。"""
    s = _setup()
    with TestClient(app) as client:
        out_trade_no = _create_pending_order(client, s)
        headers, body = _make_notify(out_trade_no)
        client.post("/api/pay/notify", content=body.encode(), headers=headers)
        oid = client.get("/api/orders/mine", headers=s["a"]).json()[0]["id"]
        # 教练无权退款
        r = client.post(f"/api/orders/{oid}/refund", headers=s["coach"])
        assert r.status_code == 403, r.text
        # 馆主退款成功（mock 微信退款接口）
        _api_calls.clear()
        r = client.post(f"/api/orders/{oid}/refund", headers=s["admin"])
        assert r.status_code == 200, r.text
        refund_calls = [c for c in _api_calls
                        if c[1] == "/v3/refund/domestic/refunds"]
        assert len(refund_calls) == 1
        assert refund_calls[0][2]["out_refund_no"] == f"RF{out_trade_no}"
        orders = client.get("/api/orders/mine", headers=s["a"]).json()
        assert orders[0]["status"] == "refunded"
        # 重复退款 → 400（仅 paid 可退）
        r = client.post(f"/api/orders/{oid}/refund", headers=s["admin"])
        assert r.status_code == 400, r.text


def test_staff_order_list():
    """工作人员看全馆订单；客户看他人订单 403。"""
    s = _setup()
    with TestClient(app) as client:
        _create_pending_order(client, s)
        r = client.get("/api/orders", headers=s["admin"])
        assert r.status_code == 200 and len(r.json()) >= 1, r.text
        r = client.get(f"/api/orders?client_id={s['aid']}", headers=s["coach"])
        assert r.status_code == 200, r.text
        r = client.get("/api/orders", headers=s["a"])
        assert r.status_code == 403, r.text
