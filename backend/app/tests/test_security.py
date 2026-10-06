# -*- coding: utf-8 -*-
"""安全专项测试：越权、token 失效、签到码泄露、重复操作。
用临时 SQLite 库，不污染正式数据。"""
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_sec.db"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# 与其他测试文件共用进程运行时，刷新已导入的 app 模块（同 test_smoke.py 注释）
for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402

if os.path.exists("test_sec.db"):
    os.remove("test_sec.db")


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_security_scenarios():
    with TestClient(app) as client:
        admin = _login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
        admin_h = _h(admin)

        # 准备：教练 + 两个客户（分属不同教练）
        client.post("/api/auth/users", json={"username": "sec_coach",
                                             "password": "pw123456", "role": "coach",
                                             "name": "安全教练"}, headers=admin_h)
        coach = _login(client, "sec_coach", "pw123456")
        coach_h = _h(coach)
        r = client.post("/api/clients", json={"name": "客户甲", "gender": "女", "age": 28,
                                              "height_cm": 165, "goal": "塑形"},
                        headers=coach_h)
        cid_a = r.json()["id"]
        # 客户甲的开机账号（user 绑定）
        r = client.post("/api/auth/users", json={"username": "userA",
                                                 "password": "pw123456", "role": "client",
                                                 "name": "客户甲", "client_id": cid_a},
                        headers=admin_h)
        assert r.status_code == 200, r.text
        usera_token = _login(client, "userA", "pw123456")
        usera_h = _h(usera_token)

        # ---- 1. 客户读课程列表：签到码必须为空 ----
        r = client.post("/api/courses", json={"title": "安全测试课", "capacity": 10,
                                              "start_time": "2026-10-10T10:00:00",
                                              "duration_min": 60}, headers=coach_h)
        assert r.status_code == 200, r.text
        course_id = r.json()["id"]
        # 教练视角：能看到签到码
        r = client.get("/api/courses", headers=coach_h)
        mine = [c for c in r.json() if c["id"] == course_id][0]
        assert mine["checkin_code"], "教练应能看到签到码"
        # 客户视角：列表和详情都拿不到签到码
        r = client.get("/api/courses", headers=usera_h)
        mine = [c for c in r.json() if c["id"] == course_id][0]
        assert mine["checkin_code"] == "", "客户不应从课程列表拿到签到码"
        r = client.get(f"/api/courses/{course_id}", headers=usera_h)
        assert r.json()["checkin_code"] == "", "客户不应从课程详情拿到签到码"
        # 客户拿不到码就无法凭空签到
        r = client.post(f"/api/courses/{course_id}/checkin", json={}, headers=usera_h)
        assert r.status_code == 400, r.text

        # ---- 2. 注销后旧 token 立即失效 ----
        r = client.get("/api/auth/me", headers=usera_h)
        assert r.status_code == 200  # 注销前 token 可用
        r = client.post("/api/me/deactivate", headers=usera_h)
        assert r.json()["ok"] is True
        r = client.get("/api/auth/me", headers=usera_h)
        assert r.status_code == 401, f"注销后旧 token 必须立即失效，实际 {r.status_code}"

        # ---- 3. 重复预约被拒 ----
        r = client.post("/api/clients", json={"name": "客户乙", "gender": "男", "age": 32,
                                              "height_cm": 178, "goal": "增肌"},
                        headers=coach_h)
        cid_b = r.json()["id"]
        r = client.post("/api/auth/users", json={"username": "userB",
                                                 "password": "pw123456", "role": "client",
                                                 "name": "客户乙", "client_id": cid_b},
                        headers=admin_h)
        assert r.status_code == 200, r.text
        userb_token = _login(client, "userB", "pw123456")
        userb_h = _h(userb_token)
        r = client.post(f"/api/courses/{course_id}/book", json={}, headers=userb_h)
        assert r.status_code == 200, r.text
        r = client.post(f"/api/courses/{course_id}/book", json={}, headers=userb_h)
        assert r.status_code == 400, "重复预约应被拒绝"

        # ---- 4. 无效课程 ID ----
        r = client.post("/api/courses/999999/book", json={}, headers=userb_h)
        assert r.status_code == 404, r.text
        r = client.post("/api/courses/999999/checkin", json={}, headers=coach_h)
        assert r.status_code == 404, r.text

        # ---- 5. 教练不能操作其他教练名下客户 ----
        client.post("/api/auth/users", json={"username": "sec_coach2",
                                             "password": "pw123456", "role": "coach",
                                             "name": "隔壁教练"}, headers=admin_h)
        coach2 = _login(client, "sec_coach2", "pw123456")
        coach2_h = _h(coach2)
        r = client.get(f"/api/clients/{cid_a}", headers=coach2_h)
        assert r.status_code == 403, r.text

    # 清理测试库（Windows 上必须先释放连接池）
    engine.dispose()
    if os.path.exists("test_sec.db"):
        os.remove("test_sec.db")
