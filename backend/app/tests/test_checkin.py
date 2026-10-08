# -*- coding: utf-8 -*-
"""每日打卡 + 上传 + 计划求助/自助生成测试。用临时 SQLite 库，不污染正式数据。"""
import io
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_checkin.db"
os.environ["UPLOAD_DIR"] = os.path.join(os.environ.get("TEMP", "/tmp"),
                                        "yoga_test_uploads_checkin")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# 与其他测试文件共用进程运行时，刷新已导入的 app 模块，
# 使 settings/engine 按本文件的 DATABASE_URL 重新初始化
for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

if os.path.exists("test_checkin.db"):
    os.remove("test_checkin.db")

_SETUP_SEQ = 0


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _setup():
    """建馆主/教练/客户A(有教练+账号)/客户B(无教练+账号)。每次唯一用户名防串号。"""
    global _SETUP_SEQ
    _SETUP_SEQ += 1
    tag = f"ck{_SETUP_SEQ}"
    with TestClient(app) as client:
        admin = _login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
        admin_h = _h(admin)
        coach_un = f"{tag}_coach"
        client.post("/api/auth/users",
                    json={"username": coach_un, "password": "pw123456",
                          "role": "coach", "name": "打卡教练"}, headers=admin_h)
        coach = _login(client, coach_un, "pw123456")
        coach_h = _h(coach)
        # 教练名下建客户 A（分配 coach_id）
        coach_id = client.get("/api/auth/me", headers=coach_h).json()["id"]
        ra = client.post("/api/clients",
                         json={"name": f"学员A{tag}", "coach_id": coach_id},
                         headers=admin_h)
        assert ra.status_code == 200, ra.text
        aid = ra.json()["id"]
        # 客户 B：无教练
        rb = client.post("/api/clients", json={"name": f"学员B{tag}"},
                         headers=admin_h)
        bid = rb.json()["id"]
        # 给 A、B 建登录账号
        ua = f"{tag}_usera"
        client.post("/api/auth/users",
                    json={"username": ua, "password": "pw123456", "role": "client",
                          "name": f"学员A{tag}", "client_id": aid}, headers=admin_h)
        ub = f"{tag}_userb"
        client.post("/api/auth/users",
                    json={"username": ub, "password": "pw123456", "role": "client",
                          "name": f"学员B{tag}", "client_id": bid}, headers=admin_h)
        return {"a": _h(_login(client, ua, "pw123456")),
                "b": _h(_login(client, ub, "pw123456")),
                "coach": coach_h, "admin": admin_h,
                "aid": aid, "bid": bid, "coach_id": coach_id}


def test_checkin_and_duplicate():
    """打卡成功；同一天同一种重复打卡 → 400。"""
    s = _setup()
    with TestClient(app) as client:
        r = client.post("/api/checkins",
                        json={"kind": "training", "note": "跑了5km"}, headers=s["a"])
        assert r.status_code == 200, r.text
        assert r.json()["kind"] == "training"
        # 训练可再打饮食，但训练重复不行
        r2 = client.post("/api/checkins", json={"kind": "diet"}, headers=s["a"])
        assert r2.status_code == 200, r2.text
        r3 = client.post("/api/checkins", json={"kind": "training"}, headers=s["a"])
        assert r3.status_code == 400, r3.text
        assert "今日已打卡" in r3.json()["detail"]


def test_checkin_mine_and_staff_view():
    """客户按月查自己；staff 代打卡；客户看他人 → 403。"""
    s = _setup()
    with TestClient(app) as client:
        client.post("/api/checkins", json={"kind": "training"}, headers=s["a"])
        # 自己按月查
        r = client.get("/api/checkins/mine?ym=2026-10", headers=s["a"])
        assert r.status_code == 200, r.text
        # staff 代打卡（饮食）
        r2 = client.post(f"/api/checkins?client_id={s['aid']}",
                         json={"kind": "diet", "note": "教练代打"}, headers=s["coach"])
        assert r2.status_code == 200, r2.text
        # staff 看客户打卡
        r3 = client.get(f"/api/clients/{s['aid']}/checkins?ym=2026-10",
                        headers=s["coach"])
        assert r3.status_code == 200 and len(r3.json()) == 2, r3.text
        # 客户 B 看 A 的 → 403
        r4 = client.get(f"/api/clients/{s['aid']}/checkins", headers=s["b"])
        assert r4.status_code == 403, r4.text
        # 客户 A 看自己的 → 200
        r5 = client.get(f"/api/clients/{s['aid']}/checkins", headers=s["a"])
        assert r5.status_code == 200, r5.text


def test_upload_validation():
    """非图片 → 400；超大 → 400；正常 png → 200 返回 path。"""
    s = _setup()
    with TestClient(app) as client:
        # 非图片
        r = client.post("/api/uploads",
                        files={"file": ("a.txt", io.BytesIO(b"hello"),
                                        "text/plain")}, headers=s["a"])
        assert r.status_code == 400, r.text
        # 超大（6MB 的假 png）
        big = io.BytesIO(b"\x89PNG" + b"x" * (6 * 1024 * 1024))
        r2 = client.post("/api/uploads",
                         files={"file": ("big.png", big, "image/png")},
                         headers=s["a"])
        assert r2.status_code == 400, r2.text
        # 正常
        small = io.BytesIO(
            b"\x89PNG\r\n\x1a\n" + b"x" * 100)
        r3 = client.post("/api/uploads",
                         files={"file": ("ok.png", small, "image/png")},
                         headers=s["a"])
        assert r3.status_code == 200, r3.text
        assert r3.json()["path"].startswith("/api/files/")


def test_plan_request_no_coach():
    """无分配教练的客户求助 → 400；有教练 → 教练收到通知。"""
    s = _setup()
    with TestClient(app) as client:
        # B 无教练
        r = client.post("/api/plan-requests",
                        json={"kind": "training", "message": "想增肌"},
                        headers=s["b"])
        assert r.status_code == 400, r.text
        assert "暂未分配教练" in r.json()["detail"]
        # A 有教练 → 通知教练
        r2 = client.post("/api/plan-requests",
                         json={"kind": "diet", "message": "减脂餐"},
                         headers=s["a"])
        assert r2.status_code == 200, r2.text
        n = client.get("/api/notifications", headers=s["coach"])
        assert n.status_code == 200, n.text
        types = [x["type"] for x in n.json()]
        assert "plan_request" in types, types


def test_client_self_generate_plan_notifies():
    """客户自助生成模板计划 → 200，且客户收到 plan_new 通知。"""
    s = _setup()
    with TestClient(app) as client:
        r = client.post(f"/api/clients/{s['aid']}/plans/generate",
                        headers=s["a"])
        assert r.status_code == 200, r.text
        n = client.get("/api/notifications", headers=s["a"])
        assert n.status_code == 200, n.text
        types = [x["type"] for x in n.json()]
        assert "plan_new" in types, types
        # 客户不能给别人生成
        r2 = client.post(f"/api/clients/{s['bid']}/plans/generate",
                         headers=s["a"])
        assert r2.status_code == 403, r2.text
