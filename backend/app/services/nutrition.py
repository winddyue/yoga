# -*- coding: utf-8 -*-
"""营养计算服务：BMR / TDEE / 三大营养素，公式参考开源项目 Fud AI 的思路。

- BMR：体脂率已知时用 Katch-McArdle，否则用 Mifflin-St Jeor
- TDEE = BMR × 活动系数
- 蛋白质 0.8–2.2g/kg 体重（按目标取值，减脂期上浮），脂肪 0.6g/kg，碳水补足剩余热量
"""
from typing import Dict, Optional

# 活动系数
ACTIVITY = {"light": 1.375, "moderate": 1.55, "active": 1.725}

# 各目标的热量调节（公斤/周变化目标换算）
GOAL_WEEKLY_KG = {"减脂": -0.5, "增肌": 0.25, "塑形": -0.25, "体态改善": 0.0}
# 各目标的蛋白质系数（g/kg 体重）
GOAL_PROTEIN = {"减脂": 2.0, "增肌": 1.8, "塑形": 1.6, "体态改善": 1.2}


def calc_bmr(weight_kg: float, height_cm: float, age: int, gender: str,
             body_fat_pct: Optional[float] = None) -> float:
    """计算基础代谢率 BMR（千卡/天）。"""
    if body_fat_pct and body_fat_pct > 0:
        # Katch-McArdle：需要瘦体重，体脂已知时更准
        lean_mass = weight_kg * (1 - body_fat_pct / 100)
        return 370 + 21.6 * lean_mass
    # Mifflin-St Jeor
    s = 5 if gender == "男" else -161
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + s


def calc_targets(weight_kg: float, height_cm: float, age: int, gender: str,
                 goal: str, activity_level: str = "moderate",
                 body_fat_pct: Optional[float] = None) -> Dict:
    """计算每日热量目标与三大营养素（克）。"""
    bmr = calc_bmr(weight_kg, height_cm, age, gender, body_fat_pct)
    tdee = bmr * ACTIVITY.get(activity_level, 1.55)
    # 目标热量 = TDEE + 每周体重变化目标换算（1kg ≈ 7700 千卡）
    calories = int(tdee + GOAL_WEEKLY_KG.get(goal, 0) * 7700 / 7)
    calories = max(calories, 1200)  # 保底，避免过低

    protein = round(GOAL_PROTEIN.get(goal, 1.6) * weight_kg, 1)
    fat = round(0.6 * weight_kg, 1)
    # 碳水 = 剩余热量 / 4
    carbs = round(max((calories - protein * 4 - fat * 9) / 4, 0), 1)
    return {
        "bmr": int(bmr),
        "tdee": int(tdee),
        "calories_target": calories,
        "protein_g": protein,
        "fat_g": fat,
        "carbs_g": carbs,
    }


# 极简中式餐单模板：按热量档位给出早/午/晚/加餐搭配，教练确认后可再调整
_MEAL_TEMPLATES = {
    "low": {  # 1500 千卡左右（减脂）
        "breakfast": ["燕麦片50g", "低脂牛奶250ml", "水煮蛋1个"],
        "lunch": ["糙米饭100g（熟重）", "鸡胸肉120g", "西兰花200g", "橄榄油5g"],
        "dinner": ["红薯150g", "清蒸鱼150g", "绿叶菜200g"],
        "snack": ["无糖酸奶150g", "苹果半个"],
    },
    "mid": {  # 1800 千卡左右（塑形/体态）
        "breakfast": ["全麦面包2片", "鸡蛋2个", "牛奶250ml"],
        "lunch": ["米饭150g（熟重）", "牛肉120g", "时蔬200g"],
        "dinner": ["面条100g（干重）", "虾仁100g", "绿叶菜200g"],
        "snack": ["香蕉1根", "坚果15g"],
    },
    "high": {  # 2200 千卡左右（增肌）
        "breakfast": ["燕麦片80g", "全脂牛奶300ml", "鸡蛋2个", "全麦面包1片"],
        "lunch": ["米饭200g（熟重）", "鸡腿肉150g", "时蔬250g"],
        "dinner": ["米饭150g（熟重）", "三文鱼150g", "西兰花200g"],
        "snack": ["酸奶200g", "坚果25g", "面包1片"],
    },
}


def generate_meals(calories_target: int) -> Dict[str, list]:
    """按热量目标选择一档餐单模板（后续可由教练确认内容来自我学习优化）。"""
    if calories_target < 1650:
        return _MEAL_TEMPLATES["low"]
    if calories_target < 2000:
        return _MEAL_TEMPLATES["mid"]
    return _MEAL_TEMPLATES["high"]


# ---------------------------------------------------------------------------
# 简化版 API（供小程序端直接调用）：固定轻度活动系数，目标按关键字解析。
# 公式参考 Fud AI 的思路：BMR 用 Mifflin-St Jeor。
# ---------------------------------------------------------------------------

def bmr(gender, age, height_cm, weight_kg):
    """基础代谢率（Mifflin-St Jeor）。gender 含"男"/"male"判男，其余按女；缺数据返回 None。"""
    try:
        w, h, a = float(weight_kg or 0), float(height_cm or 0), float(age or 0)
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0 or a <= 0:
        return None
    g = str(gender or "").strip().lower()
    s = 5 if (g in ("男", "male", "m", "man") or "男" in g) else -161
    return round(10 * w + 6.25 * h - 5 * a + s, 2)


def targets(gender, age, height_cm, weight_kg, goal_text):
    """每日热量与宏量目标。goal 含"减"→减脂，含"增"→增肌，否则保持。

    返回 {bmr, tdee, calories_target, protein_g, fat_g, carbs_g, note}，
    缺关键数据（体重/身高/年龄）时返回 None。
    """
    b = bmr(gender, age, height_cm, weight_kg)
    if b is None:
        return None
    w = float(weight_kg)
    tdee = b * 1.375
    goal = str(goal_text or "")
    if "减" in goal:
        calories = tdee - 400
        protein_per_kg, note = 2.0, "按 Mifflin 公式，减脂目标每日少400千卡"
    elif "增" in goal:
        calories = tdee + 250
        protein_per_kg, note = 1.8, "按 Mifflin 公式，增肌目标每日多250千卡"
    else:
        calories = tdee
        protein_per_kg, note = 1.6, "按 Mifflin 公式，保持当前热量摄入"
    calories_target = int(round(calories, -1))  # 四舍五入到十位
    protein_g = round(protein_per_kg * w, 1)
    fat_g = round(calories_target * 0.25 / 9, 1)
    carbs_g = round(max(calories_target - protein_g * 4 - fat_g * 9, 0) / 4, 1)
    return {
        "bmr": b, "tdee": round(tdee, 1), "calories_target": calories_target,
        "protein_g": protein_g, "fat_g": fat_g, "carbs_g": carbs_g, "note": note,
    }
