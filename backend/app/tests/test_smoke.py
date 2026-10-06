# -*- coding: utf-8 -*-
"""冒烟测试：覆盖核心链路——登录 → 建客户 → 评估 → 趋势 → 自动排课 →
手动改课 → 生成饮食 → 确认饮食 → 设置页。用临时 SQLite 库，不污染正式数据。"""
import os
import sys

# 测试前指向临时数据库（必须在 import app 之前）
os.environ["DATABASE_URL"] = "sqlite:///./test_smoke.db"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# 与 test_v2.py 共用进程运行时（无论谁先导入），刷新已导入的 app 模块，
# 使 settings/engine 按本文件的 DATABASE_URL 重新初始化，避免库文件打架
#（保留 app.tests 下的测试模块本身，避免破坏 pytest 收集）
for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402

# 清理旧的测试库，保证可重复运行
if os.path.exists("test_smoke.db"):
    os.remove("test_smoke.db")


def _login(client: TestClient, username: str, password: str) -> str:
    """登录并返回 token。"""
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_full_flow():
    # with 确保 lifespan 执行（建表 + 默认馆主账号）
    with TestClient(app) as client:
        # 1. 默认馆主账号可登录
        admin_token = _login(client, settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD)
        admin_h = {"Authorization": f"Bearer {admin_token}"}
        assert client.get("/api/auth/me", headers=admin_h).json()["role"] == "owner"

        # 2. 馆主创建教练账号
        r = client.post("/api/auth/users",
                        json={"username": "coach1", "password": "pw123456",
                              "role": "coach", "name": "李教练"},
                        headers=admin_h)
        assert r.status_code == 200, r.text

        coach_token = _login(client, "coach1", "pw123456")
        coach_h = {"Authorization": f"Bearer {coach_token}"}

        # 3. 教练新建客户
        r = client.post("/api/clients",
                        json={"name": "张三", "gender": "男", "age": 30, "height_cm": 175,
                              "phone": "13800000000", "goal": "减脂"},
                        headers=coach_h)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]

        # 3.5 登记敏感信息单独同意（合规要求，录入评估前必须）
        r = client.post("/api/consents",
                        json={"client_id": cid, "consent_type": "sensitive_info"},
                        headers=coach_h)
        assert r.status_code == 200, r.text

        # 4. 新增两次评估
        for payload in ({"date": "2026-10-01", "weight_kg": 80, "body_fat_pct": 25,
                         "waist_cm": 90, "blood_pressure": "120/80"},
                        {"date": "2026-10-06", "weight_kg": 79, "body_fat_pct": 24.2,
                         "injuries": "左膝旧伤，深蹲注意"}):
            r = client.post(f"/api/clients/{cid}/assessments", json=payload, headers=coach_h)
            assert r.status_code == 200, r.text

        # 5. 趋势数据
        r = client.get(f"/api/clients/{cid}/trends", headers=coach_h)
        assert r.json()["weight"] == [80, 79], r.text

        # 6. 健康提示
        r = client.get(f"/api/clients/{cid}/warnings", headers=coach_h)
        assert len(r.json()["warnings"]) > 0, r.text

        # 7. 自动生成训练计划
        r = client.post(f"/api/clients/{cid}/plans/generate?week_start=2026-10-06",
                        headers=coach_h)
        assert r.status_code == 200, r.text
        plan = r.json()
        assert len(plan["days"]) >= 3
        pid = plan["id"]

        # 8. 手动调整计划（加一个动作）
        days = plan["days"]
        days[0]["exercises"].append({"name": "开合跳", "sets": 3, "reps": "30"})
        r = client.put(f"/api/plans/{pid}",
                       json={"week_start": "2026-10-06", "days": days}, headers=coach_h)
        assert r.status_code == 200, r.text
        assert any(e["name"] == "开合跳" for e in r.json()["days"][0]["exercises"])

        # 9. 生成饮食方案（公式计算热量与营养素）
        r = client.post(f"/api/clients/{cid}/diets/generate",
                        json={"date": "2026-10-06", "activity_level": "moderate"},
                        headers=coach_h)
        assert r.status_code == 200, r.text
        diet = r.json()
        assert diet["calories_target"] > 1200
        assert diet["protein_g"] > 0
        assert set(diet["meals"].keys()) == {"breakfast", "lunch", "dinner", "snack"}
        did = diet["id"]

        # 10. 教练确认饮食方案
        r = client.post(f"/api/diets/{did}/confirm", headers=coach_h)
        assert r.json()["status"] == "confirmed", r.text

        # 11. 经营概况
        r = client.get("/api/dashboard", headers=admin_h)
        assert r.json()["client_count"] == 1, r.text

        # 12. 设置页：密钥只返回状态不返回明文
        r = client.get("/api/settings", headers=admin_h)
        assert r.json()["ocr_configured"] is False, r.text
        r = client.put("/api/settings", json={"ai_model": "demo-model"}, headers=admin_h)
        assert r.json()["ok"] is True

        # 13. 越权：教练2看不到教练1的客户
        client.post("/api/auth/users",
                    json={"username": "coach2", "password": "pw123456",
                          "role": "coach", "name": "王教练"},
                    headers=admin_h)
        coach2_token = _login(client, "coach2", "pw123456")
        r = client.get(f"/api/clients/{cid}",
                       headers={"Authorization": f"Bearer {coach2_token}"})
        assert r.status_code == 403, r.text

    # 清理测试库（Windows 上必须先释放连接池，否则文件被占用删不掉）
    engine.dispose()
    if os.path.exists("test_smoke.db"):
        os.remove("test_smoke.db")
