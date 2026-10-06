# -*- coding: utf-8 -*-
"""v2 测试：约课签到主流程、三角色权限越界、字段级过滤、同意校验、AI 准入。
用临时 SQLite 库，不污染正式数据。"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_v2.db"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# 与 test_smoke.py 共用进程运行时，刷新已导入的 app 模块，
# 使 settings/engine 按本文件的 DATABASE_URL 重新初始化，避免库文件打架
#（保留 app.tests 下的测试模块本身，避免破坏 pytest 收集）
for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

if os.path.exists("test_v2.db"):
    os.remove("test_v2.db")


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_v2_flow():
    with TestClient(app) as client:
        admin = _login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
        admin_h = _h(admin)

        # 建教练 + 两个客户
        client.post("/api/auth/users",
                    json={"username": "c1", "password": "pw123456",
                          "role": "coach", "name": "陈教练"}, headers=admin_h)
        coach = _login(client, "c1", "pw123456")
        coach_h = _h(coach)

        cids = []
        for name in ("学员A", "学员B"):
            r = client.post("/api/clients",
                            json={"name": name, "age": 28, "notes": "内部备注：欠费"},
                            headers=coach_h)
            assert r.status_code == 200, r.text
            cids.append(r.json()["id"])
        cid_a, cid_b = cids

        # 给学员A建客户登录账号
        r = client.post("/api/auth/users",
                        json={"username": "stuA", "password": "pw123456",
                              "role": "client", "name": "学员A", "client_id": cid_a},
                        headers=admin_h)
        assert r.status_code == 200, r.text
        stu = _login(client, "stuA", "pw123456")
        stu_h = _h(stu)

        # ---- 1. 同意校验：无同意记录时评估被拒 ----
        r = client.post(f"/api/clients/{cid_a}/assessments",
                        json={"date": "2026-10-06", "weight_kg": 70}, headers=coach_h)
        assert r.status_code == 400 and "单独授权" in r.text, r.text
        # 登记同意后通过
        r = client.post("/api/consents",
                        json={"client_id": cid_a, "consent_type": "sensitive_info"},
                        headers=coach_h)
        assert r.status_code == 200, r.text
        r = client.post(f"/api/clients/{cid_a}/assessments",
                        json={"date": "2026-10-06", "weight_kg": 70}, headers=coach_h)
        assert r.status_code == 200, r.text

        # ---- 2. 未成年人：无监护人同意被拒 ----
        r = client.post("/api/clients",
                        json={"name": "小小", "age": 12, "is_minor": True}, headers=coach_h)
        kid = r.json()["id"]
        client.post("/api/consents",
                    json={"client_id": kid, "consent_type": "sensitive_info"}, headers=coach_h)
        r = client.post(f"/api/clients/{kid}/assessments",
                        json={"date": "2026-10-06", "weight_kg": 40}, headers=coach_h)
        assert r.status_code == 400 and "监护人" in r.text, r.text

        # ---- 3. 权限越界 ----
        # 客户看不到其他客户
        r = client.get(f"/api/clients/{cid_b}", headers=stu_h)
        assert r.status_code == 403, r.text
        # 客户看不到内部备注（字段级）
        r = client.get("/api/clients/mine", headers=stu_h)
        assert r.status_code == 200, r.text
        assert r.json().get("notes", "") == "", r.text
        assert "notes" not in r.json() or r.json()["notes"] == ""
        # 教练能看到备注
        r = client.get(f"/api/clients/{cid_a}", headers=coach_h)
        assert "欠费" in r.json()["notes"], r.text
        # 客户调工作人员接口被拒
        r = client.post("/api/courses", json={"title": "x"}, headers=stu_h)
        assert r.status_code == 403, r.text

        # ---- 4. 约课签到主流程 ----
        r = client.post("/api/courses",
                        json={"title": "晨间瑜伽", "course_type": "瑜伽",
                              "start_time": "2026-10-07 07:00",
                              "end_time": "2026-10-07 08:00", "capacity": 1},
                        headers=coach_h)
        assert r.status_code == 200, r.text
        course = r.json()
        assert course["checkin_code"], r.text
        course_id, code = course["id"], course["checkin_code"]

        # 学员A预约成功
        r = client.post(f"/api/courses/{course_id}/book", headers=stu_h)
        assert r.json()["status"] == "booked", r.text
        # 学员B（教练代约）满员进候补
        r = client.post(f"/api/courses/{course_id}/book",
                        json={"client_id": cid_b}, headers=coach_h)
        assert r.json()["status"] == "waitlist", r.text
        # 学员A取消，学员B自动转正
        r = client.post(f"/api/courses/{course_id}/cancel", headers=stu_h)
        assert r.json()["promoted_client_id"] == cid_b, r.text
        # 给学员B建登录账号，扫码签到
        client.post("/api/auth/users",
                    json={"username": "stuB", "password": "pw123456",
                          "role": "client", "name": "学员B", "client_id": cid_b},
                    headers=admin_h)
        stu_b = _h(_login(client, "stuB", "pw123456"))
        # 扫码码值错误被拒
        r = client.post(f"/api/courses/{course_id}/checkin",
                        json={"code": "wrong"}, headers=stu_b)
        assert r.status_code == 400, r.text
        # 正确扫码签到
        r = client.post(f"/api/courses/{course_id}/checkin",
                        json={"code": code}, headers=stu_b)
        assert r.json()["ok"] is True and r.json()["method"] == "qr", r.text
        # 出勤率写回档案
        r = client.get(f"/api/clients/{cid_b}", headers=coach_h)
        assert r.json()["attendance_rate"] == 1.0, r.text
        # 客户看自己的约课记录
        r = client.get("/api/bookings/mine", headers=stu_h)
        assert r.status_code == 200 and len(r.json()) >= 1, r.text

        # ---- 5. AI 准入 ----
        # 未开启 -> 403
        r = client.post("/api/intake/extract", json={"text": "体重80"}, headers=coach_h)
        assert r.status_code == 403, r.text
        # 开启但未配置 -> 403
        client.put("/api/settings", json={"ai_enabled": True}, headers=admin_h)
        r = client.post("/api/intake/extract", json={"text": "体重80"}, headers=coach_h)
        assert r.status_code == 403 and "未配置" in r.text, r.text
        # 客户无订阅 -> 403（即使开启）
        r = client.post("/api/intake/extract", json={"text": "体重80"}, headers=stu_h)
        assert r.status_code == 403, r.text

        # ---- 6. 汇总页 ----
        r = client.get("/api/dashboard/me/summary", headers=stu_h)
        assert r.json()["name"] == "学员A", r.text
        r = client.get("/api/dashboard/coach/overview", headers=coach_h)
        assert "todos" in r.json() and len(r.json()["clients"]) >= 2, r.text
        r = client.get("/api/dashboard/owner/overview", headers=admin_h)
        assert r.json()["total_clients"] >= 3, r.text
        r = client.get("/api/dashboard/owner/overview", headers=coach_h)
        assert r.status_code == 403, r.text

        # ---- 7. 用户权利：导出/注销 ----
        r = client.get("/api/me/data", headers=stu_h)
        assert r.json()["profile"]["name"] == "学员A", r.text
        r = client.post("/api/me/deactivate", headers=stu_h)
        assert r.json()["ok"] is True
        r = client.post("/api/auth/login", data={"username": "stuA", "password": "pw123456"})
        assert r.status_code == 403, r.text

    if os.path.exists("test_v2.db"):
        os.remove("test_v2.db")
