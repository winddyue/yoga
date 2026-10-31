# -*- coding: utf-8 -*-
"""AI 会员订阅制测试：订阅开通/续期/过期重买、mine 接口、
AI 门禁 402、staff 不受影响、馆主商品管理。

复用 test_payment.py 的微信 mock 风格（真签名回调，不碰真实网络）。
"""
import base64
import datetime
import json
import os
import sys
import time

os.environ["DATABASE_URL"] = "sqlite:///./test_subscription.db"
os.environ["UPLOAD_DIR"] = os.path.join(os.environ.get("TEMP", "/tmp"),
                                        "yoga_test_uploads_sub")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

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

if os.path.exists("test_subscription.db"):
    os.remove("test_subscription.db")

_SETUP_SEQ = 100
_api_calls = []


def _fake_api_request(method, path, payload=None):
    _api_calls.append((method, path, payload))
    if path == "/v3/pay/transactions/jsapi":
        return {"prepay_id": f"wx_fake_prepay_{len(_api_calls)}"}
    raise AssertionError(f"unexpected wechat api call: {path}")


wxpay._api_request = _fake_api_request
wxpay._get_platform_pubkey_pem = lambda: _TEST_PUB_PEM  # noqa: E731


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login",
                    data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _bind_openid(username: str, openid: str) -> None:
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
    tag = f"sub{_SETUP_SEQ}"
    with TestClient(app) as client:
        admin = _login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
        admin_h = _h(admin)
        coach_un = f"{tag}_coach"
        client.post("/api/auth/users",
                    json={"username": coach_un, "password": "pw123456",
                          "role": "coach", "name": "订阅教练"}, headers=admin_h)
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


def _product_by_name(client: TestClient, h: dict, name: str) -> dict:
    r = client.get("/api/products", headers=h)
    assert r.status_code == 200, r.text
    items = [i for i in r.json() if i["name"] == name]
    assert items, f"{name} 不在商品列表"
    return items[0]


def _make_notify(out_trade_no: str):
    plain = {"out_trade_no": out_trade_no, "transaction_id": "4200009999",
             "trade_state": "SUCCESS",
             "amount": {"total": 2900, "currency": "CNY"},
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
    headers = {"Wechatpay-Signature": base64.b64encode(sig).decode(),
               "Wechatpay-Timestamp": ts, "Wechatpay-Nonce": rnonce,
               "Content-Type": "application/json"}
    return headers, body_str


def _buy_and_pay(client: TestClient, s: dict, product_name: str) -> str:
    """下单 + 模拟支付成功回调，返回商户订单号。"""
    _api_calls.clear()
    pid = _product_by_name(client, s["a"], product_name)["id"]
    r = client.post("/api/orders", json={"product_id": pid}, headers=s["a"])
    assert r.status_code == 200, r.text
    out_trade_no = r.json()["out_trade_no"]
    headers, body = _make_notify(out_trade_no)
    r2 = client.post("/api/pay/notify", content=body.encode(), headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["code"] == "SUCCESS"
    return out_trade_no


def _mine(client: TestClient, s: dict) -> dict:
    r = client.get("/api/subscriptions/mine", headers=s["a"])
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 订阅开通 / 续期 / 过期重买 ----------

def test_notify_creates_subscription():
    s = _setup()
    with TestClient(app) as client:
        before = datetime.datetime.now()
        _buy_and_pay(client, s, "AI 会员月卡")
        m = _mine(client, s)
        assert m["active"] is True, m
        assert m["plan_name"] == "AI 会员月卡", m
        exp = datetime.datetime.fromisoformat(m["expires_at"])
        delta = (exp - before).total_seconds()
        assert 29 * 86400 < delta < 31 * 86400, delta


def test_renewal_extends_from_current_expiry():
    """有效期内续费：顺延（max(now, 当前有效期) + 30 天）。"""
    s = _setup()
    with TestClient(app) as client:
        _buy_and_pay(client, s, "AI 会员月卡")
        exp1 = datetime.datetime.fromisoformat(_mine(client, s)["expires_at"])
        _buy_and_pay(client, s, "AI 会员月卡")
        exp2 = datetime.datetime.fromisoformat(_mine(client, s)["expires_at"])
        delta = (exp2 - exp1).total_seconds()
        assert 29 * 86400 < delta < 31 * 86400, delta
        # 同一客户只保留一条 active 记录
        db = SessionLocal()
        try:
            n = db.query(models.ClientSubscription).filter(
                models.ClientSubscription.client_id == s["aid"],
                models.ClientSubscription.status == "active").count()
            assert n == 1, n
        finally:
            db.close()


def test_repurchase_after_expiry_starts_from_now():
    """过期后重买：从 now 起算。"""
    s = _setup()
    with TestClient(app) as client:
        _buy_and_pay(client, s, "AI 会员月卡")
        db = SessionLocal()
        try:
            sub = db.query(models.ClientSubscription).filter(
                models.ClientSubscription.client_id == s["aid"],
                models.ClientSubscription.status == "active").first()
            sub.expires_at = datetime.datetime.now() - datetime.timedelta(days=1)
            db.commit()
        finally:
            db.close()
        before = datetime.datetime.now()
        _buy_and_pay(client, s, "AI 会员月卡")
        exp = datetime.datetime.fromisoformat(_mine(client, s)["expires_at"])
        delta = (exp - before).total_seconds()
        assert 29 * 86400 < delta < 31 * 86400, delta


def test_one_time_product_creates_no_subscription():
    """一次性商品支付成功不产生订阅。"""
    s = _setup()
    with TestClient(app) as client:
        r = client.post("/api/products",
                        json={"name": "单次体验券", "price_cents": 9900,
                              "kind": "one_time", "duration_days": 0,
                              "description": "一次"},
                        headers=s["admin"])
        assert r.status_code == 200, r.text
        _buy_and_pay(client, s, "单次体验券")
        assert _mine(client, s)["active"] is False


def test_mine_no_subscription():
    s = _setup()
    with TestClient(app) as client:
        m = _mine(client, s)
        assert m == {"active": False, "plan_name": None, "expires_at": None}, m


# ---------- AI 门禁 ----------

def test_ai_generate_402_without_subscription():
    s = _setup()
    with TestClient(app) as client:
        r = client.post(f"/api/clients/{s['aid']}/diets/ai-generate",
                        headers=s["a"])
        assert r.status_code == 402, r.text
        assert "开通 AI 会员后使用" in r.json()["detail"]
        r2 = client.post(f"/api/clients/{s['aid']}/plans/generate",
                         headers=s["a"])
        assert r2.status_code == 402, r2.text


def test_ai_generate_passes_with_subscription():
    """有订阅 → 门禁放行（饮食走到"缺体测"400，计划直接 200）。"""
    s = _setup()
    with TestClient(app) as client:
        _buy_and_pay(client, s, "AI 会员月卡")
        r = client.post(f"/api/clients/{s['aid']}/diets/ai-generate",
                        headers=s["a"])
        assert r.status_code == 400, r.text  # 门禁已过，卡在缺体测记录
        assert "评估" in r.json()["detail"]
        r2 = client.post(f"/api/clients/{s['aid']}/plans/generate",
                         headers=s["a"])
        assert r2.status_code == 200, r2.text


def test_staff_bypass_ai_gate():
    """工作人员调用不受订阅门禁影响。"""
    s = _setup()
    with TestClient(app) as client:
        # 教练给客户生成：饮食走到缺体测 400（非 402），计划直接 200
        r = client.post(f"/api/clients/{s['aid']}/diets/ai-generate",
                        headers=s["coach"])
        assert r.status_code == 400, r.text
        r2 = client.post(f"/api/clients/{s['aid']}/plans/generate",
                         headers=s["coach"])
        assert r2.status_code == 200, r2.text


def test_expired_subscription_blocks():
    """过期订阅 → 402。"""
    s = _setup()
    with TestClient(app) as client:
        _buy_and_pay(client, s, "AI 会员月卡")
        db = SessionLocal()
        try:
            sub = db.query(models.ClientSubscription).filter(
                models.ClientSubscription.client_id == s["aid"],
                models.ClientSubscription.status == "active").first()
            sub.expires_at = datetime.datetime.now() - datetime.timedelta(days=1)
            db.commit()
        finally:
            db.close()
        r = client.post(f"/api/clients/{s['aid']}/plans/generate",
                        headers=s["a"])
        assert r.status_code == 402, r.text


# ---------- 馆主商品管理 ----------

def test_product_admin_owner_only():
    s = _setup()
    with TestClient(app) as client:
        body = {"name": "测试套餐", "price_cents": 100, "duration_days": 7}
        for h in (s["a"], s["coach"]):
            r = client.post("/api/products", json=body, headers=h)
            assert r.status_code == 403, (h, r.text)
            r2 = client.patch("/api/products/1", json={"price_cents": 1},
                              headers=h)
            assert r2.status_code == 403, r2.text
        r = client.post("/api/products", json=body, headers=s["admin"])
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["price_cents"] == 100 and d["duration_days"] == 7
        assert d["kind"] == "subscription" and d["active"] is True


def test_price_change_only_affects_new_orders():
    """改价后新订单用新价；老订单金额不变（下单时快照）。"""
    s = _setup()
    with TestClient(app) as client:
        r = client.post("/api/products",
                        json={"name": "调价测试卡", "price_cents": 1000,
                              "duration_days": 30},
                        headers=s["admin"])
        pid = r.json()["id"]
        # 老订单：1000 分，下单并支付
        r1 = client.post("/api/orders", json={"product_id": pid},
                         headers=s["a"])
        assert r1.status_code == 200, r1.text
        old_no = r1.json()["out_trade_no"]
        # 馆主改价到 2000 分
        rp = client.patch(f"/api/products/{pid}",
                          json={"price_cents": 2000}, headers=s["admin"])
        assert rp.status_code == 200 and rp.json()["price_cents"] == 2000
        # 先把老订单付掉，避免复用窗口干扰
        headers, body = _make_notify(old_no)
        client.post("/api/pay/notify", content=body.encode(), headers=headers)
        # 新订单用新价
        r2 = client.post("/api/orders", json={"product_id": pid},
                         headers=s["a"])
        assert r2.status_code == 200, r2.text
        orders = client.get("/api/orders/mine", headers=s["a"]).json()
        amounts = {o["out_trade_no"]: o["amount_cents"] for o in orders}
        assert amounts[old_no] == 1000, amounts
        assert amounts[r2.json()["out_trade_no"]] == 2000, amounts


def test_deactivate_hides_product():
    """下架后商品列表不再出现，下单 404。"""
    s = _setup()
    with TestClient(app) as client:
        r = client.post("/api/products",
                        json={"name": "下架测试卡", "price_cents": 100,
                              "duration_days": 30},
                        headers=s["admin"])
        pid = r.json()["id"]
        assert any(i["name"] == "下架测试卡"
                   for i in client.get("/api/products",
                                       headers=s["a"]).json())
        rp = client.patch(f"/api/products/{pid}", json={"active": False},
                          headers=s["admin"])
        assert rp.status_code == 200 and rp.json()["active"] is False
        names = [i["name"] for i in client.get("/api/products",
                                              headers=s["a"]).json()]
        assert "下架测试卡" not in names
        r2 = client.post("/api/orders", json={"product_id": pid},
                         headers=s["a"])
        assert r2.status_code == 404, r2.text


def test_buy_subscription_503_when_unconfigured():
    """未配置微信支付时买订阅仍 503。"""
    s = _setup()
    old = settings.WXPAY_APPID
    settings.WXPAY_APPID = ""
    try:
        with TestClient(app) as client:
            pid = _product_by_name(client, s["a"], "AI 会员月卡")["id"]
            r = client.post("/api/orders", json={"product_id": pid},
                            headers=s["a"])
            assert r.status_code == 503, r.text
    finally:
        settings.WXPAY_APPID = old
