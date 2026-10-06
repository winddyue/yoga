# -*- coding: utf-8 -*-
"""微信登录 + 签到时间窗测试。本地用 WX_DEV_MOCK 模拟 code2session，不依赖真实微信。"""
import datetime
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_wx.db"
os.environ["WX_DEV_MOCK"] = "true"   # mock:xxx 形式的 code 换 mock openid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# 与其他测试文件共用进程运行时，刷新已导入的 app 模块（同 test_smoke.py 注释）
for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402

if os.path.exists("test_wx.db"):
    os.remove("test_wx.db")


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_wx_login_and_checkin_window():
    with TestClient(app) as client:
        assert settings.WX_DEV_MOCK is True
        admin_h = _h(_login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD))

        # 准备教练 + 客户账号
        client.post("/api/auth/users", json={"username": "wx_coach", "password": "pw123456",
                                             "role": "coach", "name": "绑定教练"},
                    headers=admin_h)
        coach_h = _h(_login(client, "wx_coach", "pw123456"))
        r = client.post("/api/clients", json={"name": "微信客户", "gender": "女", "age": 26,
                                              "height_cm": 163, "goal": "塑形"},
                        headers=coach_h)
        cid = r.json()["id"]
        client.post("/api/auth/users", json={"username": "wx_user", "password": "pw123456",
                                             "role": "client", "name": "微信客户",
                                             "client_id": cid}, headers=admin_h)
        stu_h = _h(_login(client, "wx_user", "pw123456"))

        # ---- 1. 未绑定：wx-login 返回 404 ----
        r = client.post("/api/auth/wx-login", json={"code": "mock:device-1"})
        assert r.status_code == 404, r.text
        assert "绑定" in r.json()["detail"]

        # ---- 2. 登录态绑定微信 ----
        r = client.post("/api/auth/wx-bind", json={"code": "mock:device-1"}, headers=stu_h)
        assert r.status_code == 200 and r.json()["bound"], r.text

        # ---- 3. 免密登录：直接换到 token，可用 ----
        r = client.post("/api/auth/wx-login", json={"code": "mock:device-1"})
        assert r.status_code == 200, r.text
        wx_token = r.json()["access_token"]
        r = client.get("/api/auth/me", headers=_h(wx_token))
        assert r.status_code == 200 and r.json()["username"] == "wx_user", r.text

        # ---- 4. 一个微信不能绑两个账号 ----
        client.post("/api/auth/users", json={"username": "wx_user2", "password": "pw123456",
                                             "role": "client", "name": "另一客户",
                                             "client_id": cid}, headers=admin_h)
        stu2_h = _h(_login(client, "wx_user2", "pw123456"))
        r = client.post("/api/auth/wx-bind", json={"code": "mock:device-1"}, headers=stu2_h)
        assert r.status_code == 400, r.text

        # ---- 5. 签到时间窗 ----
        def _mk_course(minutes_from_now):
            start = (datetime.datetime.now() +
                     datetime.timedelta(minutes=minutes_from_now)).strftime("%Y-%m-%d %H:%M")
            r = client.post("/api/courses", json={"title": "窗口测试课", "capacity": 10,
                                                  "start_time": start},
                            headers=coach_h)
            assert r.status_code == 200, r.text
            return r.json()["id"], r.json()["checkin_code"]

        # 5a. 课程两小时后才开始：客户扫码被时间窗拒绝
        cid_course, code = _mk_course(120)
        client.post(f"/api/courses/{cid_course}/book", json={}, headers=stu_h)
        r = client.post(f"/api/courses/{cid_course}/checkin", json={"code": code},
                        headers=stu_h)
        assert r.status_code == 400 and "签到时间" in r.json()["detail"], r.text
        # 教练手动补签不受时间窗限制
        r = client.post(f"/api/courses/{cid_course}/checkin", json={"client_id": cid},
                        headers=coach_h)
        assert r.status_code == 200 and r.json()["method"] == "manual", r.text

        # 5b. 课程 5 分钟后开始（窗口内）：客户扫码成功
        cid_course2, code2 = _mk_course(5)
        client.post(f"/api/courses/{cid_course2}/book", json={}, headers=stu_h)
        r = client.post(f"/api/courses/{cid_course2}/checkin", json={"code": code2},
                        headers=stu_h)
        assert r.status_code == 200 and r.json()["method"] == "qr", r.text

        # ---- 6. 签到二维码：教练可取，客户 403 ----
        r = client.get(f"/api/courses/{cid_course2}/qrcode", headers=coach_h)
        assert r.status_code == 200, r.text
        assert r.json()["content"] == f"yoga:checkin:{cid_course2}:{code2}"
        assert r.json()["png_base64"][:20]  # PNG base64 非空
        r = client.get(f"/api/courses/{cid_course2}/qrcode", headers=stu_h)
        assert r.status_code == 403, r.text

    # 清理测试库（Windows 上必须先释放连接池）
    engine.dispose()
    if os.path.exists("test_wx.db"):
        os.remove("test_wx.db")
