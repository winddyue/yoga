# -*- coding: utf-8 -*-
"""图表与汇总测试：trends 含腰围/臀围、me/charts 数据包与权限、
coach/overview 新增字段（距上次评估天数/建议动作）与 action 推导。
用临时 SQLite 库，不污染正式数据。"""
import os
import sys
from datetime import datetime, timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_charts.db"
# 上传目录指向临时目录，避免测试产物污染仓库（backend/uploads/）
os.environ["UPLOAD_DIR"] = os.path.join(os.environ.get("TEMP", "/tmp"),
                                        "yoga_test_uploads")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# 与其他测试文件共用进程运行时，刷新已导入的 app 模块，
# 使 settings/engine 按本文件的 DATABASE_URL 重新初始化
#（保留 app.tests 下的测试模块本身，避免破坏 pytest 收集）
for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app import models  # noqa: E402
from app.main import app  # noqa: E402

if os.path.exists("test_charts.db"):
    os.remove("test_charts.db")


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _d(days_ago: int) -> str:
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def test_charts_flow():
    with TestClient(app) as client:
        admin = _login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
        admin_h = _h(admin)

        client.post("/api/auth/users",
                    json={"username": "cc", "password": "pw123456",
                          "role": "coach", "name": "图教练"}, headers=admin_h)
        coach = _login(client, "cc", "pw123456")
        coach_h = _h(coach)

        cids = {}
        for name in ("甲", "乙", "丙", "丁"):
            r = client.post("/api/clients", json={"name": name}, headers=coach_h)
            assert r.status_code == 200, r.text
            cids[name] = r.json()["id"]

        # 甲的客户登录账号
        client.post("/api/auth/users",
                    json={"username": "stuJia", "password": "pw123456",
                          "role": "client", "name": "甲",
                          "client_id": cids["甲"]}, headers=admin_h)
        stu = _login(client, "stuJia", "pw123456")
        stu_h = _h(stu)

        for cid in cids.values():
            r = client.post("/api/consents",
                            json={"client_id": cid, "consent_type": "sensitive_info"},
                            headers=coach_h)
            assert r.status_code == 200, r.text

        # 甲：3 次评估（最近一次 70 天前）；乙/丙：10 天前各 1 次；丁：无评估
        for n, w, bf, wa, hip in [(90, 70, 25, 80, 95), (80, 68, 23, 78, 94),
                                 (70, 66, 21, 76, 93)]:
            r = client.post(f"/api/clients/{cids['甲']}/assessments",
                            json={"date": _d(n), "weight_kg": w, "body_fat_pct": bf,
                                  "waist_cm": wa, "hip_cm": hip}, headers=coach_h)
            assert r.status_code == 200, r.text
        for name in ("乙", "丙"):
            r = client.post(f"/api/clients/{cids[name]}/assessments",
                            json={"date": _d(10), "weight_kg": 65, "body_fat_pct": 22,
                                  "waist_cm": 75, "hip_cm": 92}, headers=coach_h)
            assert r.status_code == 200, r.text

        # ---- 1. trends 含 waist/hip；越权 403 ----
        r = client.get(f"/api/clients/{cids['甲']}/trends", headers=stu_h)
        assert r.status_code == 200, r.text
        tr = r.json()
        assert tr["dates"] == [_d(90), _d(80), _d(70)], tr["dates"]
        assert tr["waist"] == [80, 78, 76] and tr["hip"] == [95, 94, 93], tr
        r = client.get(f"/api/clients/{cids['乙']}/trends", headers=stu_h)
        assert r.status_code == 403, r.text

        # ---- 2. me/charts 结构与权限 ----
        r = client.get("/api/dashboard/me/charts", headers=stu_h)
        assert r.status_code == 200, r.text
        ch = r.json()
        assert set(ch.keys()) == {"trends", "changes", "monthly_attendance"}, ch.keys()
        assert ch["changes"] == {"weight": -4.0, "body_fat": -4.0, "waist": -4.0}, ch["changes"]
        assert len(ch["monthly_attendance"]) == 6
        for m in ch["monthly_attendance"]:
            assert set(m.keys()) == {"month", "attended", "total", "rate"}, m
        # 教练调 me/charts → 403；未登录 → 401
        assert client.get("/api/dashboard/me/charts", headers=coach_h).status_code == 403
        assert client.get("/api/dashboard/me/charts").status_code == 401

        # ---- 3. 出勤数据：过去课程签到/爽约计入，未来课程不计 ----
        def _dt_past(n):
            return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d %H:%M")

        past1 = client.post("/api/courses",
                            json={"title": "过去课1", "start_time": _dt_past(10)},
                            headers=coach_h).json()["id"]
        past2 = client.post("/api/courses",
                            json={"title": "过去课2", "start_time": _dt_past(40)},
                            headers=coach_h).json()["id"]
        fut = client.post("/api/courses",
                          json={"title": "未来课",
                                "start_time": (datetime.now() + timedelta(days=10))
                                .strftime("%Y-%m-%d %H:%M")},
                          headers=coach_h).json()["id"]
        for cid_course in (past1, past2, fut):
            r = client.post(f"/api/courses/{cid_course}/book",
                            json={"client_id": cids["甲"]}, headers=coach_h)
            assert r.status_code == 200, r.text
        r = client.post(f"/api/courses/{past1}/checkin",
                        json={"client_id": cids["甲"]}, headers=coach_h)
        assert r.status_code == 200, r.text
        r = client.post(f"/api/courses/{past2}/mark-noshow", headers=coach_h)
        assert r.status_code == 200, r.text

        # 签到逻辑会回写出勤率，这里按场景固定期望值
        db = SessionLocal()
        try:
            for name, rate in (("甲", 0.8), ("乙", 0.3), ("丙", 0.9), ("丁", 0.0)):
                db.query(models.Client).filter(
                    models.Client.id == cids[name]).update({"attendance_rate": rate})
            db.commit()
        finally:
            db.close()

        r = client.get("/api/dashboard/me/charts", headers=stu_h)
        ma = {m["month"]: m for m in r.json()["monthly_attendance"]}
        mk1, mk2 = _dt_past(10)[:7], _dt_past(40)[:7]
        assert ma[mk1]["attended"] == 1 and ma[mk1]["total"] == 1 \
            and ma[mk1]["rate"] == 1.0, ma[mk1]
        assert ma[mk2]["attended"] == 0 and ma[mk2]["total"] == 1 \
            and ma[mk2]["rate"] == 0, ma[mk2]

        # ---- 4. coach/overview 新增字段与 action 推导 ----
        r = client.get("/api/dashboard/coach/overview", headers=coach_h)
        assert r.status_code == 200, r.text
        items = {c["name"]: c for c in r.json()["clients"]}
        # 甲：70 天未评估→红灯，出勤 0.8 → 安排复测
        assert items["甲"]["days_since_assessment"] == 70, items["甲"]
        assert items["甲"]["status"] == "red" \
            and items["甲"]["action"] == "安排复测", items["甲"]
        # 乙：10 天前评估、出勤 0.3 → 黄灯 → 提醒复测/关注出勤
        assert items["乙"]["status"] == "yellow" \
            and items["乙"]["action"] == "提醒复测/关注出勤", items["乙"]
        # 丙：10 天前评估、出勤 0.9 → 绿灯 → 无动作
        assert items["丙"]["status"] == "green" \
            and items["丙"]["action"] == "", items["丙"]
        # 丁：无评估→红灯，出勤 0 → 出勤低，需跟进；天数为 null
        assert items["丁"]["days_since_assessment"] is None, items["丁"]
        assert items["丁"]["status"] == "red" \
            and items["丁"]["action"] == "出勤低，需跟进", items["丁"]
