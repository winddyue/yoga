# -*- coding: utf-8 -*-
"""客户上课记录接口 + coach/overview created_at 字段测试。
用临时 SQLite 库，不污染正式数据。"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_bookings_view.db"
os.environ["UPLOAD_DIR"] = os.path.join(os.environ.get("TEMP", "/tmp"),
                                        "yoga_test_uploads")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# 与其他测试文件共用进程运行时，刷新已导入的 app 模块，
# 使 settings/engine 按本文件的 DATABASE_URL 重新初始化
for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

if os.path.exists("test_bookings_view.db"):
    os.remove("test_bookings_view.db")


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


_SETUP_SEQ = 0


def _setup():
    """建馆主/教练/客户A(教练名下)/客户B，课程×2，A 预约两节。返回句柄。
    每次调用用唯一用户名，避免同库多次建档串号。"""
    global _SETUP_SEQ
    _SETUP_SEQ += 1
    tag = f"{_SETUP_SEQ}"
    with TestClient(app) as client:
        admin = _login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
        admin_h = _h(admin)
        coach_un = f"bvcoach{tag}"
        client.post("/api/auth/users",
                    json={"username": coach_un, "password": "pw123456",
                          "role": "coach", "name": "视教练"}, headers=admin_h)
        coach = _login(client, coach_un, "pw123456")
        coach_h = _h(coach)
        # 客户 A：教练名下；客户 B：馆主直属（coach_id 为空）
        ra = client.post("/api/clients", json={"name": "学员A"}, headers=coach_h)
        assert ra.status_code == 200, ra.text
        aid = ra.json()["id"]
        rb = client.post("/api/clients", json={"name": "学员B"}, headers=admin_h)
        bid = rb.json()["id"]
        # 客户 A 的登录账号（绑定档案）
        ca_un = f"bva{tag}"
        client.post("/api/auth/users",
                    json={"username": ca_un, "password": "pw123456",
                          "role": "client", "name": "学员A", "client_id": aid},
                    headers=admin_h)
        ca = _login(client, ca_un, "pw123456")
        # 两节课：教练代 A 预约（时间倒序验证用不同的 start_time）
        c1 = client.post("/api/courses",
                         json={"title": "晨间瑜伽", "start_time": "2026-10-01 07:30",
                               "end_time": "2026-10-01 08:30"},
                         headers=coach_h).json()["id"]
        c2 = client.post("/api/courses",
                         json={"title": "晚间流瑜伽", "start_time": "2026-10-08 19:00",
                               "end_time": "2026-10-08 20:00"},
                         headers=coach_h).json()["id"]
        r1 = client.post(f"/api/courses/{c1}/book", json={"client_id": aid},
                         headers=coach_h)
        assert r1.status_code == 200, r1.text
        r2 = client.post(f"/api/courses/{c2}/book", json={"client_id": aid},
                         headers=coach_h)
        assert r2.status_code == 200, r2.text
        return {"admin_h": admin_h, "coach_h": coach_h, "ca_h": _h(ca),
                "aid": aid, "bid": bid}


def test_coach_can_view_own_client_bookings():
    s = _setup()
    with TestClient(app) as client:
        r = client.get(f"/api/clients/{s['aid']}/bookings", headers=s["coach_h"])
        assert r.status_code == 200, r.text
        rows = r.json()
        assert len(rows) == 2
        # 按课程开始时间倒序：晚间流瑜伽在前
        assert rows[0]["course_title"] == "晚间流瑜伽"
        assert rows[1]["course_title"] == "晨间瑜伽"
        assert set(rows[0].keys()) == {"course_title", "start_time", "status"}
        assert rows[0]["status"] == "booked"
        assert rows[0]["start_time"] == "2026-10-08 19:00"


def test_client_cannot_view_other_bookings():
    s = _setup()
    with TestClient(app) as client:
        # 学员 A 看学员 B 的记录 → 403
        r = client.get(f"/api/clients/{s['bid']}/bookings", headers=s["ca_h"])
        assert r.status_code == 403, r.text
        # 学员 A 看自己的 → 200
        r = client.get(f"/api/clients/{s['aid']}/bookings", headers=s["ca_h"])
        assert r.status_code == 200, r.text
        assert len(r.json()) == 2


def test_coach_overview_has_created_at():
    s = _setup()
    with TestClient(app) as client:
        r = client.get("/api/dashboard/coach/overview", headers=s["coach_h"])
        assert r.status_code == 200, r.text
        items = r.json()["clients"]
        assert items, "教练名下应有客户"
        for it in items:
            assert "created_at" in it, f"缺少 created_at: {it}"
            # ISO 日期字符串 YYYY-MM-DD
            parts = it["created_at"].split("-")
            assert len(parts) == 3 and len(parts[0]) == 4, it["created_at"]
