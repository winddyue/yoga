# -*- coding: utf-8 -*-
"""AI 饮食双轨制 + 站内通知测试：ai-generate 全流程（mock LLM）、
通知落库、confirm 触发通知、权限、通知 API、预约/签到通知触发。
用临时 SQLite 库，不污染正式数据。"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_ai_notify.db"
os.environ["UPLOAD_DIR"] = os.path.join(os.environ.get("TEMP", "/tmp"),
                                        "yoga_test_uploads")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import llm  # noqa: E402

if os.path.exists("test_ai_notify.db"):
    os.remove("test_ai_notify.db")


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


FAKE_DIET = {
    "meals": {"breakfast": ["燕麦50g"], "lunch": ["鸡胸肉150g"],
              "dinner": ["蔬菜沙拉"], "snack": ["酸奶200ml"]},
    "calories_target": 1800, "protein_g": 120, "fat_g": 50, "carbs_g": 200,
}


def _fake_generate(profile):
    assert profile["weight_kg"] == 68
    return dict(FAKE_DIET)


_setup_seq = [0]


def _setup(monkeypatch):
    """建账号/客户/评估/AI 订阅，返回 (client, admin_h, coach_h, client_h, client_id)。"""
    monkeypatch.setattr(llm, "generate_diet_plan", _fake_generate)
    _setup_seq[0] += 1
    tag = _setup_seq[0]  # 同一 DB 文件多测试复用，用户名必须唯一
    coach_u, client_u = f"ncoach{tag}", f"nclient{tag}"
    c = TestClient(app)
    c.__enter__()  # 触发 lifespan：建表、默认馆主账号、预置 AI 套餐
    # admin 已由启动逻辑创建（admin/admin123）
    admin_t = _login(c, "admin", "admin123")
    admin_h = _h(admin_t)
    # 教练 + 客户账号
    r = c.post("/api/auth/users", json={"username": coach_u, "password": "pw123456",
                                        "role": "coach", "name": "牛教练"}, headers=admin_h)
    assert r.status_code == 200, r.text
    coach_t = _login(c, coach_u, "pw123456")
    db = SessionLocal()
    coach = db.query(models.User).filter(models.User.username == coach_u).first()
    coach_id = coach.id
    db.close()
    r = c.post("/api/clients", json={"name": f"通知测试客{tag}", "gender": "女",
                                     "coach_id": coach_id}, headers=admin_h)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    r = c.post("/api/auth/users", json={"username": client_u, "password": "pw123456",
                                        "role": "client", "name": f"通知测试客{tag}",
                                        "client_id": cid}, headers=admin_h)
    assert r.status_code == 200, r.text
    client_t = _login(c, client_u, "pw123456")
    # 评估（含体重）
    db = SessionLocal()
    db.add(models.Assessment(client_id=cid, date="2026-10-01", weight_kg=68,
                             body_fat_pct=30, waist_cm=80))
    db.commit()
    db.close()
    # AI 配置：开启 + 专业版订阅（含 plan_diet）
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")
    r = c.put("/api/settings", json={"ai_enabled": True,
                                     "ai_api_url": "http://x",
                                     "ai_model": "m"}, headers=admin_h)
    assert r.status_code == 200, r.text
    r = c.get("/api/ai/plans", headers=admin_h)
    pro = [p for p in r.json() if p["name"] == "专业版"][0]
    r = c.post("/api/ai/subscriptions",
               json={"plan_id": pro["id"], "days": 30, "status": "active"},
               headers=admin_h)
    assert r.status_code == 200, r.text
    return c, admin_h, _h(coach_t), _h(client_t), cid, tag, coach_u, client_u


def _notifs(db, user_id):
    return (db.query(models.Notification)
            .filter(models.Notification.user_id == user_id).all())


def test_ai_generate_flow(monkeypatch):
    c, admin_h, coach_h, client_h, cid, tag, coach_u, client_u = _setup(monkeypatch)
    r = c.post(f"/api/clients/{cid}/diets/ai-generate", json={}, headers=client_h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "ai_draft" and d["source"] == "ai", d
    assert d["disclaimer"] and "不构成医疗建议" in d["disclaimer"], d
    assert d["meals"]["breakfast"] == ["燕麦50g"], d
    # 通知：客户 + 教练各一条
    db = SessionLocal()
    try:
        cu = db.query(models.User).filter(models.User.username == client_u).first()
        co = db.query(models.User).filter(models.User.username == coach_u).first()
        cn, kn = _notifs(db, cu.id), _notifs(db, co.id)
        assert len(cn) == 1 and cn[0].type == "diet_ai_ready", [n.type for n in cn]
        assert len(kn) == 1 and kn[0].type == "diet_ai_ready", [n.type for n in kn]
        assert "待教练确认" in cn[0].body or "待确认" in cn[0].title
        # 用量已记录
        assert db.query(models.AiUsage).filter(
            models.AiUsage.kind == "plan_diet").count() == 1
    finally:
        db.close()
    engine.dispose()


def test_ai_generate_llm_not_configured(monkeypatch):
    c, admin_h, coach_h, client_h, cid, tag, coach_u, client_u = _setup(monkeypatch)

    def _boom(profile):
        raise llm.LlmNotConfigured("nope")
    monkeypatch.setattr(llm, "generate_diet_plan", _boom)
    r = c.post(f"/api/clients/{cid}/diets/ai-generate", json={}, headers=client_h)
    assert r.status_code == 503 and "馆主尚未配置" in r.text, r.text
    engine.dispose()


def test_confirm_flow_and_permissions(monkeypatch):
    c, admin_h, coach_h, client_h, cid, tag, coach_u, client_u = _setup(monkeypatch)
    r = c.post(f"/api/clients/{cid}/diets/ai-generate", json={}, headers=client_h)
    did = r.json()["id"]
    # 客户调 confirm -> 403
    r = c.post(f"/api/diets/{did}/confirm", json={}, headers=client_h)
    assert r.status_code == 403, r.text
    # 教练确认（附带微调）
    meals = {"breakfast": ["包子2个"], "lunch": [], "dinner": [], "snack": []}
    r = c.post(f"/api/diets/{did}/confirm", json={"meals": meals}, headers=coach_h)
    assert r.status_code == 200 and r.json()["status"] == "confirmed", r.text
    assert r.json()["meals"]["breakfast"] == ["包子2个"], r.text
    # 客户收到 diet_confirmed 通知
    db = SessionLocal()
    try:
        cu = db.query(models.User).filter(models.User.username == client_u).first()
        types = [n.type for n in _notifs(db, cu.id)]
        assert "diet_confirmed" in types, types
    finally:
        db.close()
    engine.dispose()


def test_diet_visibility_permissions(monkeypatch):
    c, admin_h, coach_h, client_h, cid, tag, coach_u, client_u = _setup(monkeypatch)
    # 另一个客户
    r = c.post("/api/clients", json={"name": "路人", "gender": "女"}, headers=admin_h)
    other_cid = r.json()["id"]
    c.post("/api/auth/users", json={"username": f"nother{tag}", "password": "pw123456",
                                    "role": "client", "name": "路人",
                                    "client_id": other_cid}, headers=admin_h)
    other_h = _h(_login(c, f"nother{tag}", "pw123456"))
    # 看他人饮食 -> 403；给他人生成 -> 403
    assert c.get(f"/api/clients/{cid}/diets", headers=other_h).status_code == 403
    assert c.post(f"/api/clients/{cid}/diets/ai-generate",
                  json={}, headers=other_h).status_code == 403
    engine.dispose()


def test_notifications_api(monkeypatch):
    c, admin_h, coach_h, client_h, cid, tag, coach_u, client_u = _setup(monkeypatch)
    c.post(f"/api/clients/{cid}/diets/ai-generate", json={}, headers=client_h)
    # 未读数
    r = c.get("/api/notifications/unread-count", headers=client_h)
    assert r.status_code == 200 and r.json()["unread"] == 1, r.text
    # 列表
    r = c.get("/api/notifications", headers=client_h)
    assert len(r.json()) == 1 and r.json()[0]["is_read"] is False
    nid = r.json()[0]["id"]
    # 教练不能标客户的通知
    assert c.post(f"/api/notifications/{nid}/read", headers=coach_h).status_code == 404
    # 标已读
    assert c.post(f"/api/notifications/{nid}/read", headers=client_h).status_code == 200
    r = c.get("/api/notifications/unread-count", headers=client_h)
    assert r.json()["unread"] == 0, r.text
    # 全部已读
    c.post(f"/api/clients/{cid}/diets/ai-generate", json={}, headers=client_h)
    r = c.get("/api/notifications/unread-count", headers=client_h)
    assert r.json()["unread"] == 1
    assert c.post("/api/notifications/read-all", headers=client_h).status_code == 200
    r = c.get("/api/notifications/unread-count", headers=client_h)
    assert r.json()["unread"] == 0, r.text
    engine.dispose()


def test_booking_checkin_notifications(monkeypatch):
    c, admin_h, coach_h, client_h, cid, tag, coach_u, client_u = _setup(monkeypatch)
    # 建课程（容量 1）
    from datetime import datetime, timedelta
    start = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    r = c.post("/api/courses", json={"title": "通知测试课", "start_time": start,
                                     "capacity": 1}, headers=coach_h)
    assert r.status_code == 200, r.text
    course_id = r.json()["id"]
    # 客户预约 -> 收到 booking_created
    r = c.post(f"/api/courses/{course_id}/book", json={}, headers=client_h)
    assert r.status_code == 200 and r.json()["status"] == "booked", r.text
    # 第二个客户候补（挂到同一教练名下，保证教练可见）
    db = SessionLocal()
    coach_user = db.query(models.User).filter(models.User.username == coach_u).first()
    db.add(models.Client(name=f"候补客{tag}", gender="女", coach_id=coach_user.id))
    db.commit()
    wc = db.query(models.Client).filter(models.Client.name == f"候补客{tag}").first()
    wcid = wc.id
    db.close()
    c.post("/api/auth/users", json={"username": f"nwait{tag}", "password": "pw123456",
                                    "role": "client", "name": f"候补客{tag}",
                                    "client_id": wcid}, headers=admin_h)
    wait_h = _h(_login(c, f"nwait{tag}", "pw123456"))
    r = c.post(f"/api/courses/{course_id}/book", json={}, headers=wait_h)
    assert r.json()["status"] == "waitlist", r.text
    # 取消 -> 候补转正，候补客户收到 booking_promoted
    r = c.post(f"/api/courses/{course_id}/cancel", json={}, headers=client_h)
    assert r.json()["promoted_client_id"] == wcid, r.text
    db = SessionLocal()
    try:
        wu = db.query(models.User).filter(models.User.username == f"nwait{tag}").first()
        types = [n.type for n in _notifs(db, wu.id)]
        assert "booking_promoted" in types, types
        cu = db.query(models.User).filter(models.User.username == client_u).first()
        ctypes = [n.type for n in _notifs(db, cu.id)]
        assert "booking_created" in ctypes, ctypes
    finally:
        db.close()
    # 签到 -> 教练收到 checkin 通知（教练手动签到，绕过时间窗）
    db = SessionLocal()
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    code = course.checkin_code
    db.close()
    r = c.post(f"/api/courses/{course_id}/checkin",
               json={"client_id": wcid}, headers=coach_h)
    assert r.status_code == 200, r.text
    db = SessionLocal()
    try:
        co = db.query(models.User).filter(models.User.username == coach_u).first()
        ktypes = [n.type for n in _notifs(db, co.id)]
        assert "checkin" in ktypes, ktypes
    finally:
        db.close()
    engine.dispose()
