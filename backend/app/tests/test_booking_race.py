# -*- coding: utf-8 -*-
"""预约并发与座位计数器测试：原子抢座不超卖、取消转正交接、
候补签到人工放行、重复预约拒绝、Alembic 迁移幂等。
用临时 SQLite 库，不污染正式数据。"""
import os
import subprocess
import sys
import threading

os.environ["DATABASE_URL"] = "sqlite:///./test_race.db"
os.environ["UPLOAD_DIR"] = os.path.join(os.environ.get("TEMP", "/tmp"),
                                        "yoga_test_uploads_race")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# 与其他测试文件共用进程运行时，刷新已导入的 app 模块，
# 使 settings/engine 按本文件的 DATABASE_URL 重新初始化
#（保留 app.tests 下的测试模块本身，避免破坏 pytest 收集）
for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402
from app.main import app  # noqa: E402

if os.path.exists("test_race.db"):
    os.remove("test_race.db")


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _setup(client: TestClient, tag: str, capacity: int):
    """建教练 + N 个客户，返回 (coach_h, course_id, [client_ids])。"""
    admin = _login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
    admin_h = _h(admin)
    client.post("/api/auth/users",
                json={"username": f"coach_{tag}", "password": "pw123456",
                      "role": "coach", "name": f"教练{tag}"}, headers=admin_h)
    coach_h = _h(_login(client, f"coach_{tag}", "pw123456"))
    r = client.post("/api/courses",
                    json={"title": f"并发课{tag}", "course_type": "瑜伽",
                          "start_time": "2026-10-09 07:00",
                          "end_time": "2026-10-09 08:00",
                          "capacity": capacity}, headers=coach_h)
    assert r.status_code == 200, r.text
    course_id = r.json()["id"]
    cids = []
    for i in range(10):
        r = client.post("/api/clients", json={"name": f"学员{tag}-{i}"},
                        headers=coach_h)
        assert r.status_code == 200, r.text
        cids.append(r.json()["id"])
    return coach_h, course_id, cids


def _seats(course_id: int) -> int:
    db = SessionLocal()
    try:
        return db.query(models.Course).filter(
            models.Course.id == course_id).first().booked_seats
    finally:
        db.close()


def test_concurrent_book_no_oversell():
    """10 线程同时抢 3 个名额：恰好 3 个 booked，其余 waitlist，计数器一致。"""
    with TestClient(app) as client:
        coach_h, course_id, cids = _setup(client, "race", 3)
        statuses, errors = [], []

        def _book(i: int):
            try:
                r = client.post(f"/api/courses/{course_id}/book",
                                json={"client_id": cids[i]}, headers=coach_h)
                statuses.append(r.json().get("status"))
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))

        threads = [threading.Thread(target=_book, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        assert not errors, errors
        assert len(statuses) == 10, statuses
        assert statuses.count("booked") == 3, statuses
        assert statuses.count("waitlist") == 7, statuses
        assert _seats(course_id) == 3


def test_cancel_promote_and_release():
    """取消已约→候补转正（座位过户，计数器不动）；再取消→释放座位。"""
    with TestClient(app) as client:
        coach_h, course_id, cids = _setup(client, "cancel", 1)
        a, b, c = cids[0], cids[1], cids[2]
        r = client.post(f"/api/courses/{course_id}/book",
                        json={"client_id": a}, headers=coach_h)
        assert r.json()["status"] == "booked", r.text
        r = client.post(f"/api/courses/{course_id}/book",
                        json={"client_id": b}, headers=coach_h)
        assert r.json()["status"] == "waitlist", r.text
        assert _seats(course_id) == 1
        # A 取消：B 转正，计数器仍为 1（过户而非释放）
        r = client.post(f"/api/courses/{course_id}/cancel",
                        json={"client_id": a}, headers=coach_h)
        assert r.json()["promoted_client_id"] == b, r.text
        assert _seats(course_id) == 1
        # B 再取消：无候补，释放座位
        r = client.post(f"/api/courses/{course_id}/cancel",
                        json={"client_id": b}, headers=coach_h)
        assert r.json()["promoted_client_id"] is None, r.text
        assert _seats(course_id) == 0
        # C 能正常约上
        r = client.post(f"/api/courses/{course_id}/book",
                        json={"client_id": c}, headers=coach_h)
        assert r.json()["status"] == "booked", r.text
        assert _seats(course_id) == 1


def test_waitlist_checkin_takes_seat():
    """候补被教练手动签到 = 人工放行：计数器如实 +1（可超 capacity）。"""
    with TestClient(app) as client:
        coach_h, course_id, cids = _setup(client, "override", 1)
        a, b = cids[0], cids[1]
        client.post(f"/api/courses/{course_id}/book",
                    json={"client_id": a}, headers=coach_h)
        client.post(f"/api/courses/{course_id}/book",
                    json={"client_id": b}, headers=coach_h)
        r = client.post(f"/api/courses/{course_id}/checkin",
                        json={"client_id": b}, headers=coach_h)
        assert r.json()["ok"] is True and r.json()["method"] == "manual", r.text
        assert _seats(course_id) == 2  # 教练显式放行，如实记录


def test_duplicate_book_rejected():
    """同一客户重复预约被拒；取消后可重新约（部分唯一索引只约束有效预约）。"""
    with TestClient(app) as client:
        coach_h, course_id, cids = _setup(client, "dup", 5)
        a = cids[0]
        r = client.post(f"/api/courses/{course_id}/book",
                        json={"client_id": a}, headers=coach_h)
        assert r.json()["status"] == "booked", r.text
        r = client.post(f"/api/courses/{course_id}/book",
                        json={"client_id": a}, headers=coach_h)
        assert r.status_code == 400 and "已预约" in r.text, r.text
        # 取消后重新预约允许
        client.post(f"/api/courses/{course_id}/cancel",
                    json={"client_id": a}, headers=coach_h)
        r = client.post(f"/api/courses/{course_id}/book",
                        json={"client_id": a}, headers=coach_h)
        assert r.json()["status"] == "booked", r.text


def test_alembic_upgrade_idempotent():
    """alembic upgrade head 可重复执行；列与索引存在。"""
    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    env = dict(os.environ, DATABASE_URL="sqlite:///./test_race.db")
    for _ in range(2):
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini",
             "upgrade", "head"],
            cwd=backend_dir, env=env, capture_output=True, text=True,
            timeout=120)
        assert r.returncode == 0, r.stderr[-2000:]
    from sqlalchemy import inspect as sa_inspect  # noqa: E402
    insp = sa_inspect(engine)
    assert "booked_seats" in {c["name"] for c in insp.get_columns("courses")}
    assert "uq_booking_active" in {i["name"] for i in insp.get_indexes("bookings")}


def test_alembic_upgrade_old_db():
    """模拟老库（无 booked_seats 列、无索引）：迁移补列、回填计数、建索引。"""
    import sqlalchemy as sa  # noqa: E402
    with TestClient(app) as client:
        coach_h, course_id, cids = _setup(client, "old", 2)
        client.post(f"/api/courses/{course_id}/book",
                    json={"client_id": cids[0]}, headers=coach_h)
    # 退回到"老库"状态：删列、删索引，并清除版本戳，
    # 使 upgrade head 真正重新执行本迁移
    with engine.begin() as conn:
        conn.execute(sa.text("ALTER TABLE courses DROP COLUMN booked_seats"))
        conn.execute(sa.text("DROP INDEX uq_booking_active"))
        conn.execute(sa.text("DROP TABLE IF EXISTS alembic_version"))
    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    env = dict(os.environ, DATABASE_URL="sqlite:///./test_race.db")
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=backend_dir, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    # 列回来了，计数按已有预约回填为 1，索引重建
    assert _seats(course_id) == 1
    from sqlalchemy import inspect as sa_inspect  # noqa: E402
    insp = sa_inspect(engine)
    assert "uq_booking_active" in {i["name"] for i in insp.get_indexes("bookings")}
