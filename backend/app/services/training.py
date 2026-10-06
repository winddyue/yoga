# -*- coding: utf-8 -*-
"""训练计划生成服务：按客户目标自动编排一周计划，教练可在前端手动调整。

设计参考 wger 的训练编排思路，但只保留最简核心：按目标选模板，
动作库为内置极简清单（后续可在设置中扩展）。
"""
from typing import Dict, List

# 内置极简动作库：按目标分组，每组给出每周训练日安排
_PLAN_TEMPLATES: Dict[str, List[Dict]] = {
    "减脂": [
        {"day": "周一", "time": "", "exercises": [
            {"name": "跑步机快走", "sets": 1, "reps": "30分钟"},
            {"name": "深蹲", "sets": 3, "reps": "15"},
            {"name": "俯卧撑", "sets": 3, "reps": "12"},
            {"name": "平板支撑", "sets": 3, "reps": "45秒"}]},
        {"day": "周三", "time": "", "exercises": [
            {"name": "动感单车", "sets": 1, "reps": "30分钟"},
            {"name": "弓步蹲", "sets": 3, "reps": "12/腿"},
            {"name": "哑铃推举", "sets": 3, "reps": "12"},
            {"name": "卷腹", "sets": 3, "reps": "20"}]},
        {"day": "周五", "time": "", "exercises": [
            {"name": "椭圆机", "sets": 1, "reps": "25分钟"},
            {"name": "硬拉（轻）", "sets": 3, "reps": "12"},
            {"name": "划船", "sets": 3, "reps": "12"},
            {"name": "拉伸放松", "sets": 1, "reps": "10分钟"}]},
    ],
    "增肌": [
        {"day": "周一", "time": "", "exercises": [
            {"name": "杠铃卧推", "sets": 4, "reps": "8-10"},
            {"name": "哑铃飞鸟", "sets": 3, "reps": "12"},
            {"name": "双杠臂屈伸", "sets": 3, "reps": "10"}]},
        {"day": "周三", "time": "", "exercises": [
            {"name": "引体向上", "sets": 4, "reps": "力竭"},
            {"name": "杠铃划船", "sets": 4, "reps": "10"},
            {"name": "弯举", "sets": 3, "reps": "12"}]},
        {"day": "周五", "time": "", "exercises": [
            {"name": "深蹲", "sets": 4, "reps": "8-10"},
            {"name": "腿举", "sets": 3, "reps": "12"},
            {"name": "站姿提踵", "sets": 3, "reps": "15"}]},
    ],
    "塑形": [
        {"day": "周二", "time": "", "exercises": [
            {"name": "瑜伽流（拜日式）", "sets": 1, "reps": "20分钟"},
            {"name": "臀桥", "sets": 3, "reps": "15"},
            {"name": "侧平板", "sets": 3, "reps": "30秒/侧"}]},
        {"day": "周四", "time": "", "exercises": [
            {"name": "普拉提核心序列", "sets": 1, "reps": "20分钟"},
            {"name": "深蹲", "sets": 3, "reps": "15"},
            {"name": "弹力带划船", "sets": 3, "reps": "15"}]},
        {"day": "周六", "time": "", "exercises": [
            {"name": "快走", "sets": 1, "reps": "30分钟"},
            {"name": "猫牛式", "sets": 3, "reps": "10"},
            {"name": "全身拉伸", "sets": 1, "reps": "10分钟"}]},
    ],
    "体态改善": [
        {"day": "周二", "time": "", "exercises": [
            {"name": "靠墙站立", "sets": 3, "reps": "2分钟"},
            {"name": "弹力带外旋", "sets": 3, "reps": "15"},
            {"name": "死虫式", "sets": 3, "reps": "10/侧"}]},
        {"day": "周四", "time": "", "exercises": [
            {"name": "泡沫轴放松上背", "sets": 1, "reps": "10分钟"},
            {"name": "面拉", "sets": 3, "reps": "15"},
            {"name": "臀桥", "sets": 3, "reps": "15"}]},
    ],
}


def generate_plan(goal: str) -> List[Dict]:
    """按训练目标返回一周计划模板；未知目标默认返回减脂模板。"""
    import copy
    return copy.deepcopy(_PLAN_TEMPLATES.get(goal, _PLAN_TEMPLATES["减脂"]))


def health_warnings(assessment) -> List[str]:
    """根据最新评估给出健康风险提示（展示用，不做医疗诊断）。"""
    warnings = []
    if assessment.blood_pressure:
        warnings.append(f"血压记录为 {assessment.blood_pressure}，训练前请确认适宜强度。")
    if assessment.injuries:
        warnings.append(f"注意事项：{assessment.injuries}")
    if assessment.resting_hr and assessment.resting_hr > 100:
        warnings.append("静息心率偏高，建议先咨询医生再安排高强度训练。")
    return warnings
