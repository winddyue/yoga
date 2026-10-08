# -*- coding: utf-8 -*-
"""并发预约测试：多线程同时预约同一课程，验证不超卖、无重复预约、
候补逻辑不受影响。用临时 SQLite 库，不污染正式数据。"""
import os
import sys
import threading
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_concurrency.db"
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

from app.auth import create_access_token  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402

if os.path.exists("test_concurrency.db"):
    os.remove("test_concurrency.db")


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _setup(client: TestClient, admin_h: dict, n_clients: int,
           capacity: int) -> tuple[int, list[str]]:
    """建一门课 + n 个客户及登录账号；直接签发 token（省掉 n 次 bcrypt 登录）。"""
    r = client.post("/api/courses",
                    json={"title": "并发测试课", "capacity": capacity,
                          "start_time": "2026-12-01 10:00"},
                    headers=admin_h)
    assert r.status_code == 200, r.text
    course_id = r.json()["id"]
    tokens = []
    for i in range(n_clients):
        r = client.post("/api/clients", json={"name": f"并发{i}"}, headers=admin_h)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        uname = f"conc_{uuid.uuid4().hex[:12]}"
        r = client.post("/api/auth/users",
                        json={"username": uname, "password": "pw123456",
                              "role": "client", "name": f"并发{i}", "client_id": cid},
                        headers=admin_h)
        assert r.status_code == 200, r.text
        tokens.append(create_access_token(uname))
    return course_id, tokens


def _book_many(course_id: int, tokens: list[str]) -> list[int]:
    """每个 token 一个线程同时预约；每个线程用独立 TestClient。"""
    statuses: list[int] = []
    lock = threading.Lock()

    def work(tok: str):
        c = TestClient(app)
        r = c.post(f"/api/courses/{course_id}/book", json={}, headers=_h(tok))
        with lock:
            statuses.append(r.status_code)

    threads = [threading.Thread(target=work, args=(t,)) for t in tokens]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    assert all(not t.is_alive() for t in threads), "有线程超时未结束"
    return statuses


def _roster(client: TestClient, admin_h: dict, course_id: int) -> list[dict]:
    r = client.get(f"/api/courses/{course_id}/roster", headers=admin_h)
    assert r.status_code == 200, r.text
    return r.json()


def test_concurrent_booking_no_oversell():
    """15 人同时抢 5 个名额：booked 恰为 5，无超卖，无重复预约，其余进候补。"""
    with TestClient(app) as client:
        admin_h = _h(_login(client, settings.ADMIN_USERNAME,
                            settings.ADMIN_PASSWORD))
        course_id, tokens = _setup(client, admin_h, 15, 5)
        statuses = _book_many(course_id, tokens)
        assert all(s == 200 for s in statuses), statuses

        rows = _roster(client, admin_h, course_id)
        booked = [x for x in rows if x["status"] == "booked"]
        waitlist = [x for x in rows if x["status"] == "waitlist"]
        assert len(booked) == 5, f"超卖或名额浪费：booked={len(booked)}"
        assert len(waitlist) == 10, f"候补数不对：{len(waitlist)}"
        active = [x for x in rows
                  if x["status"] in ("booked", "waitlist", "checked_in")]
        cids = [x["client_id"] for x in active]
        assert len(cids) == len(set(cids)) == 15, "存在重复预约"


def test_concurrent_duplicate_booking():
    """同一客户 5 个线程同时预约：只有 1 个成功，其余 400，无重复行。"""
    with TestClient(app) as client:
        admin_h = _h(_login(client, settings.ADMIN_USERNAME,
                            settings.ADMIN_PASSWORD))
        course_id, tokens = _setup(client, admin_h, 1, 5)
        statuses = _book_many(course_id, [tokens[0]] * 5)
        assert statuses.count(200) == 1, statuses
        assert statuses.count(400) == 4, statuses

        rows = _roster(client, admin_h, course_id)
        active = [x for x in rows
                  if x["status"] in ("booked", "waitlist", "checked_in")]
        assert len(active) == 1, f"重复预约穿透：{active}"


def test_waitlist_promotion_still_works():
    """候补逻辑不受影响：取消 1 个已约，候补第一位自动转正。"""
    with TestClient(app) as client:
        admin_h = _h(_login(client, settings.ADMIN_USERNAME,
                            settings.ADMIN_PASSWORD))
        course_id, tokens = _setup(client, admin_h, 3, 2)
        for t in tokens:
            r = client.post(f"/api/courses/{course_id}/book", json={},
                            headers=_h(t))
            assert r.status_code == 200, r.text
        rows = _roster(client, admin_h, course_id)
        assert sum(1 for x in rows if x["status"] == "booked") == 2
        assert sum(1 for x in rows if x["status"] == "waitlist") == 1

        r = client.post(f"/api/courses/{course_id}/cancel", json={},
                        headers=_h(tokens[0]))
        assert r.status_code == 200, r.text
        assert r.json()["promoted_client_id"] is not None

        rows = _roster(client, admin_h, course_id)
        by_status: dict[str, int] = {}
        for x in rows:
            by_status[x["status"]] = by_status.get(x["status"], 0) + 1
        assert by_status.get("booked") == 2, by_status
        assert by_status.get("waitlist", 0) == 0, by_status
        assert by_status.get("cancelled") == 1, by_status
