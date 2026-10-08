# -*- coding: utf-8 -*-
"""v3 测试：P0 安全修复回归 + AI 订阅改造（门店级 AiPlan/AiSubscription/AiFeatureGate）。
用临时 SQLite 库，不污染正式数据。"""
import io
import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_v3.db"
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

from app.config import settings, validate_prod, is_prod  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402
from app.main import app  # noqa: E402
from app.services import ai_gate  # noqa: E402

if os.path.exists("test_v3.db"):
    os.remove("test_v3.db")


def _login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tiny_png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, format="PNG")
    return buf.getvalue()


def test_v3_flow():
    with TestClient(app) as client:
        admin = _login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
        admin_h = _h(admin)

        # 建教练 + 两个客户 + 客户账号
        client.post("/api/auth/users",
                    json={"username": "c3", "password": "pw123456",
                          "role": "coach", "name": "王教练"}, headers=admin_h)
        coach = _login(client, "c3", "pw123456")
        coach_h = _h(coach)
        cids = []
        for name in ("学员C", "学员D"):
            r = client.post("/api/clients", json={"name": name, "age": 30}, headers=coach_h)
            cids.append(r.json()["id"])
        cid_c, cid_d = cids
        for uname, cid in (("stuC", cid_c), ("stuD", cid_d)):
            client.post("/api/auth/users",
                        json={"username": uname, "password": "pw123456",
                              "role": "client", "client_id": cid}, headers=admin_h)
        stu_c = _h(_login(client, "stuC", "pw123456"))
        stu_d = _h(_login(client, "stuD", "pw123456"))

        # ---- A1. 签到码：客户看不到，教练看得到 ----
        r = client.post("/api/courses",
                        json={"title": "测试课", "start_time": "2026-10-08 07:00",
                              "end_time": "2026-10-08 08:00", "capacity": 10},
                        headers=coach_h)
        course_id = r.json()["id"]
        assert r.json()["checkin_code"], r.text
        r = client.get("/api/courses", headers=stu_c)
        assert r.status_code == 200
        assert all("checkin_code" not in c for c in r.json()), r.text
        r = client.get(f"/api/courses/{course_id}", headers=stu_c)
        assert "checkin_code" not in r.json(), r.text
        r = client.get("/api/courses", headers=coach_h)
        assert all(c.get("checkin_code") for c in r.json()), r.text

        # ---- A2. 注销后旧 token 立即 401 ----
        client.post("/api/auth/users",
                    json={"username": "tmp1", "password": "pw123456",
                          "role": "coach", "name": "临时"}, headers=admin_h)
        tmp_tok = _login(client, "tmp1", "pw123456")
        r = client.get("/api/auth/me", headers=_h(tmp_tok))
        assert r.status_code == 200, r.text
        client.post("/api/me/deactivate", headers=_h(tmp_tok))
        r = client.get("/api/auth/me", headers=_h(tmp_tok))
        assert r.status_code == 401, r.text

        # ---- A3. 文件鉴权下载 ----
        png = _tiny_png()
        r = client.post(f"/api/clients/{cid_c}/photo",
                        files={"file": ("t.png", png, "image/png")}, headers=coach_h)
        assert r.status_code == 200, r.text
        dl_url = r.json()["download_url"]
        fname = dl_url.rsplit("/", 1)[-1]
        # 教练可下
        r = client.get(dl_url, headers=coach_h)
        assert r.status_code == 200 and r.content == png, r.text
        # 未登录 401
        r = client.get(dl_url)
        assert r.status_code in (401, 403), r.text
        # 未关联评估的文件，客户不可下
        r = client.get(dl_url, headers=stu_c)
        assert r.status_code == 403, r.text
        # 伪造图片被拒
        r = client.post(f"/api/clients/{cid_c}/photo",
                        files={"file": ("x.png", b"not-an-image", "image/png")},
                        headers=coach_h)
        assert r.status_code == 400, r.text
        # 超大文件被拒
        big = b"0" * (settings.MAX_UPLOAD_BYTES + 1)
        r = client.post(f"/api/clients/{cid_c}/photo",
                        files={"file": ("b.png", big, "image/png")}, headers=coach_h)
        assert r.status_code == 400, r.text
        # 关联评估后：本人可下，他人不可下
        client.post("/api/consents",
                    json={"client_id": cid_c, "consent_type": "sensitive_info"},
                    headers=coach_h)
        r = client.post(f"/api/clients/{cid_c}/photo",
                        files={"file": ("t2.png", png, "image/png")}, headers=coach_h)
        photo_path = r.json()["photo_path"]
        fname2 = r.json()["download_url"].rsplit("/", 1)[-1]
        r = client.post(f"/api/clients/{cid_c}/assessments",
                        json={"date": "2026-10-06", "weight_kg": 65,
                              "photo_path": photo_path}, headers=coach_h)
        assert r.status_code == 200, r.text
        r = client.get(f"/api/files/{fname2}", headers=stu_c)
        assert r.status_code == 200, r.text
        r = client.get(f"/api/files/{fname2}", headers=stu_d)
        assert r.status_code == 403, r.text
        # 目录穿越被拒
        r = client.get("/api/files/..%2Fmain.py", headers=coach_h)
        assert r.status_code in (400, 404), r.text

        # ---- A4. 生产安全基线 ----
        assert is_prod() is False  # 测试默认开发模式
        validate_prod()  # 开发模式只警告，不抛错
        old_env, old_prod = settings.ENV, settings.PROD
        settings.ENV = "prod"
        try:
            assert is_prod() is True
            try:
                validate_prod()
                raise AssertionError("生产模式+默认密钥应报错退出")
            except RuntimeError as e:
                assert "SECRET_KEY" in str(e), str(e)
        finally:
            settings.ENV, settings.PROD = old_env, old_prod

        # ---- A5. CORS 白名单 ----
        cors = [m for m in app.user_middleware
                if "CORSMiddleware" in str(m.cls)]
        assert cors, "缺少 CORS 中间件"
        origins = cors[0].kwargs.get("allow_origins", [])
        assert "*" not in origins and len(origins) > 0, origins

        # ---- A6. 计划/饮食写接口 ----
        # v9.2 起：模板计划生成对客户开放自助（只能给自己），教练可用；
        # 手动改计划、饮食生成仍仅工作人员
        r = client.post(f"/api/clients/{cid_c}/plans/generate",
                        json={}, headers=stu_c)
        assert r.status_code == 200, r.text
        r = client.post(f"/api/clients/{cid_c}/plans/generate",
                        json={}, headers=coach_h)
        assert r.status_code == 200, r.text
        plan_id = r.json()["id"]
        r = client.put(f"/api/plans/{plan_id}",
                       json={"week_start": "", "days": []}, headers=stu_c)
        assert r.status_code == 403, r.text
        r = client.post(f"/api/clients/{cid_c}/diets/generate",
                        json={"date": "2026-10-07", "activity_level": "轻"},
                        headers=stu_c)
        assert r.status_code == 403, r.text
        # 客户读接口仍可用
        r = client.get(f"/api/clients/{cid_c}/plans", headers=stu_c)
        assert r.status_code == 200, r.text

        # ---- B. AI 订阅改造 ----
        # 套餐预置 3 档
        r = client.get("/api/ai/plans", headers=coach_h)
        assert r.status_code == 200 and len(r.json()) == 3, r.text
        names = [p["name"] for p in r.json()]
        assert names == ["免费版", "专业版", "旗舰版"], names
        free_plan = r.json()[0]
        assert free_plan["features"]["extract"] is True
        assert free_plan["features"]["ocr"] is False
        # 馆主可改套餐，教练不行
        r = client.put(f"/api/ai/plans/{free_plan['id']}",
                       json={"monthly_price": 29}, headers=coach_h)
        assert r.status_code == 403, r.text
        r = client.put(f"/api/ai/plans/{free_plan['id']}",
                       json={"monthly_price": 29, "features": {"ocr": True}},
                       headers=admin_h)
        assert r.status_code == 200 and r.json()["monthly_price"] == 29, r.text
        assert r.json()["features"]["ocr"] is True
        # 改回（不影响后续断言）
        client.put(f"/api/ai/plans/{free_plan['id']}",
                   json={"monthly_price": 0,
                         "features": {"extract": True, "ocr": False, "voice": False,
                                      "plan_diet": False, "summary": False}},
                   headers=admin_h)

        # AI 门控：先配好大模型（只 mock 配置，不调真实 LLM）
        settings.AI_API_KEY = "test-key"
        client.put("/api/settings",
                   json={"ai_enabled": True, "ai_api_url": "http://x",
                         "ai_model": "m"}, headers=admin_h)
        # 无订阅 -> 403
        r = client.post("/api/intake/extract", json={"text": "体重70"}, headers=coach_h)
        assert r.status_code == 403 and "订阅" in r.text, r.text
        # 手动开通免费版订阅（门店级）
        r = client.post("/api/ai/subscriptions",
                        json={"plan_id": free_plan["id"], "days": 30,
                              "status": "active"}, headers=coach_h)
        assert r.status_code == 200, r.text
        # 用量面板
        r = client.get("/api/ai/subscription", headers=admin_h)
        assert r.status_code == 200
        assert r.json()["subscription"]["plan_name"] == "免费版", r.text
        assert r.json()["quotas"]["extract"]["remaining"] == 50, r.text
        # 门控通过（直接调 gate，不触发真实 LLM）
        db = SessionLocal()
        try:
            user = db.query(models.User).filter(models.User.username == "c3").first()
            ai_gate.check_ai_access(db, user, "extract")  # 不抛错即通过
            # 免费版不含 ocr -> 403
            try:
                ai_gate.check_ai_access(db, user, "ocr")
                raise AssertionError("免费版 ocr 应被拒")
            except Exception as e:
                assert getattr(e, "status_code", None) == 403, e
        finally:
            db.close()
        # 用量超限 -> 403（免费版 llm 50 次）
        db = SessionLocal()
        try:
            for _ in range(50):
                ai_gate.record_usage(db, 1, "extract")
        finally:
            db.close()
        r = client.post("/api/intake/extract", json={"text": "体重70"}, headers=coach_h)
        assert r.status_code == 403 and "额度" in r.text, r.text
        # 馆主汇总页含 AI 订阅信息（在过期测试之前，此时订阅有效）
        r = client.get("/api/dashboard/owner/overview", headers=admin_h)
        assert r.json()["ai_subscription"]["plan_name"] == "免费版", r.text
        assert "extract" in r.json()["ai_quotas"], r.text
        # 过期订阅 -> 403：直接写一条过期记录
        db = SessionLocal()
        try:
            past = __import__("datetime").datetime.now() - __import__("datetime").timedelta(days=1)
            for s in db.query(models.AiSubscription).all():
                s.status = "expired"
                s.expires_at = past
            db.commit()
        finally:
            db.close()
        r = client.post("/api/intake/extract", json={"text": "体重70"}, headers=coach_h)
        assert r.status_code == 403 and "订阅" in r.text, r.text
        # 用量统计（馆主）
        r = client.get("/api/ai/usage", headers=admin_h)
        assert r.status_code == 200 and len(r.json()) >= 1, r.text
        r = client.get("/api/ai/usage", headers=coach_h)
        assert r.status_code == 403, r.text
        settings.AI_API_KEY = ""

    # 清理测试库（Windows 上必须先释放连接池，否则文件被占用删不掉）
    engine.dispose()
    if os.path.exists("test_v3.db"):
        os.remove("test_v3.db")
