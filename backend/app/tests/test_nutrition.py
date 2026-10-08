# -*- coding: utf-8 -*-
"""营养公式（Fud AI 思路）+ 动作库 + 营养目标/月度总结接口测试。用临时 SQLite 库。"""
import datetime
import os
import sys

os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "sqlite:///./test_nutrition.db")
os.environ["UPLOAD_DIR"] = os.path.join(os.environ.get("TEMP", "/tmp"),
                                        "yoga_test_uploads")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

for _mod in [m for m in list(sys.modules)
             if (m == "app" or m.startswith("app.")) and not m.startswith("app.tests")]:
    del sys.modules[_mod]

from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.data.exercises import CATEGORIES, EXERCISES  # noqa: E402
from app.main import app  # noqa: E402
from app.services.nutrition import bmr, targets  # noqa: E402

if os.path.exists("test_nutrition.db"):
    os.remove("test_nutrition.db")


def _login(c, username, password):
    r = c.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- 纯函数 ----------

def test_bmr_known_value():
    # 男30岁175cm70kg = 10*70+6.25*175-5*30+5 = 1648.75
    assert bmr("男", 30, 175, 70) == 1648.75
    assert bmr("male", 30, 175, 70) == 1648.75
    # 女30岁165cm60kg = 600+1031.25-150-161 = 1320.25
    assert bmr("女", 30, 165, 60) == 1320.25
    assert bmr("", 30, 165, 60) == 1320.25  # 缺性别按女


def test_bmr_missing_returns_none():
    assert bmr("男", 30, 175, 0) is None
    assert bmr("男", 30, 0, 70) is None
    assert bmr("男", 0, 175, 70) is None
    assert bmr("男", None, 175, 70) is None


def test_targets_goal_parsing():
    b = 1648.75
    tdee = round(b * 1.375, 1)
    r = targets("男", 30, 175, 70, "减脂")
    assert r["bmr"] == b and r["tdee"] == tdee
    assert r["calories_target"] == int(round(tdee - 400, -1))
    assert r["protein_g"] == 140.0  # 2.0g/kg
    assert "少400千卡" in r["note"]
    r = targets("男", 30, 175, 70, "增肌塑形")
    assert r["calories_target"] == int(round(tdee + 250, -1))
    assert r["protein_g"] == 126.0  # 1.8g/kg
    r = targets("男", 30, 175, 70, "保持体型")
    assert r["calories_target"] == int(round(tdee, -1))
    assert r["protein_g"] == 112.0  # 1.6g/kg


def test_targets_macro_sums_to_calories():
    for goal in ("减脂", "增肌", "塑形"):
        r = targets("女", 28, 165, 60, goal)
        total = r["protein_g"] * 4 + r["fat_g"] * 9 + r["carbs_g"] * 4
        assert abs(total - r["calories_target"]) < 2, (goal, total, r)
    assert set(r.keys()) == {"bmr", "tdee", "calories_target", "protein_g",
                             "fat_g", "carbs_g", "note"}


def test_targets_missing_returns_none():
    assert targets("女", 28, 165, 0, "减脂") is None
    assert targets("女", 28, 0, 60, "减脂") is None
    assert targets("女", 0, 165, 60, "减脂") is None


def test_exercises_static():
    assert len(EXERCISES) == 36
    assert set(CATEGORIES) == {"瑜伽", "力量", "有氧", "拉伸"}
    for e in EXERCISES:
        assert set(e.keys()) == {"name", "category", "muscle"}
        assert e["category"] in CATEGORIES


# ---------- 接口 ----------

def _setup():
    _setup.seq += 1
    tag = _setup.seq
    c = TestClient(app)
    c.__enter__()
    admin_h = _h(_login(c, "admin", "admin123"))
    # 档案齐全的客户
    r = c.post("/api/clients", json={"name": f"营养客{tag}", "gender": "女", "age": 28,
                                     "height_cm": 165, "goal": "减脂"}, headers=admin_h)
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    r = c.post("/api/auth/users", json={"username": f"nutclient{tag}", "password": "pw123456",
                                        "role": "client", "name": f"营养客{tag}",
                                        "client_id": cid}, headers=admin_h)
    assert r.status_code == 200, r.text
    client_h = _h(_login(c, f"nutclient{tag}", "pw123456"))
    # 档案不全的客户（无身高/年龄/评估）
    r = c.post("/api/clients", json={"name": f"缺档案客{tag}", "gender": "男"},
               headers=admin_h)
    cid2 = r.json()["id"]
    # 本月两次评估：体重下降
    today = datetime.date.today()
    d1 = (today - datetime.timedelta(days=6)).isoformat()
    d2 = today.isoformat()
    db = SessionLocal()
    db.add(models.Assessment(client_id=cid, date=d1, weight_kg=60, body_fat_pct=30))
    db.add(models.Assessment(client_id=cid, date=d2, weight_kg=58.5, body_fat_pct=29))
    course = models.Course(title="测试课", start_time=d2 + " 10:00",
                           end_time=d2 + " 11:00")
    db.add(course)
    db.commit()
    db.add(models.CheckIn(client_id=cid, course_id=course.id,
                          checked_at=datetime.datetime.now()))
    db.commit()
    db.close()
    return c, admin_h, client_h, cid, cid2


_setup.seq = 0


def test_exercises_api():
    c, admin_h, _, _, _ = _setup()
    r = c.get("/api/exercises", headers=admin_h)
    assert r.status_code == 200
    data = r.json()
    assert len(data["exercises"]) == 36
    assert set(data["categories"]) == {"瑜伽", "力量", "有氧", "拉伸"}
    # 未登录 401
    assert c.get("/api/exercises").status_code == 401


def test_nutrition_targets_api():
    c, admin_h, _, cid, cid2 = _setup()
    r = c.get(f"/api/clients/{cid}/nutrition-targets", headers=admin_h)
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["calories_target"] == 1410  # 女28/165/58.5kg减脂
    assert t["protein_g"] == round(2.0 * 58.5, 1)
    total = t["protein_g"] * 4 + t["fat_g"] * 9 + t["carbs_g"] * 4
    assert abs(total - t["calories_target"]) < 2
    # 档案不全 → 400
    r = c.get(f"/api/clients/{cid2}/nutrition-targets", headers=admin_h)
    assert r.status_code == 400
    assert "档案信息不全" in r.json()["detail"]


def test_monthly_summary_with_data():
    c, _, client_h, _, _ = _setup()
    r = c.get("/api/dashboard/me/monthly", headers=client_h)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["assess_count"] == 2
    assert s["weight_change"] == -1.5
    assert s["body_fat_change"] == -1.0
    assert s["checkin_count"] == 1
    assert "2次体测" in s["text"] and "体重下降1.5kg" in s["text"]
    assert "继续保持" in s["text"]


def test_monthly_summary_no_data():
    c, admin_h, _, _, _ = _setup()
    _setup.seq += 1
    tag = _setup.seq
    r = c.post("/api/clients", json={"name": f"空白客{tag}", "gender": "女", "age": 30,
                                     "height_cm": 160, "goal": "塑形"}, headers=admin_h)
    cid = r.json()["id"]
    r = c.post("/api/auth/users", json={"username": f"blankclient{tag}", "password": "pw123456",
                                        "role": "client", "name": f"空白客{tag}",
                                        "client_id": cid}, headers=admin_h)
    h = _h(_login(c, f"blankclient{tag}", "pw123456"))
    r = c.get("/api/dashboard/me/monthly", headers=h)
    assert r.status_code == 200
    s = r.json()
    assert s["assess_count"] == 0
    assert s["weight_change"] is None
    assert s["text"] == "先记录一次体测吧"
