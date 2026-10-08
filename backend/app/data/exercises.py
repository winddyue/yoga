# -*- coding: utf-8 -*-
"""动作库：静态列表，供训练计划编排时点选（借鉴 wger 的思路，只取最精华的常用动作）。

每项 {name, category, muscle}，category ∈ 瑜伽/力量/有氧/拉伸。
"""
EXERCISES = [
    # 瑜伽（16）
    {"name": "下犬式", "category": "瑜伽", "muscle": "全身"},
    {"name": "上犬式", "category": "瑜伽", "muscle": "背"},
    {"name": "战士一式", "category": "瑜伽", "muscle": "腿/臀"},
    {"name": "战士二式", "category": "瑜伽", "muscle": "腿/臀"},
    {"name": "战士三式", "category": "瑜伽", "muscle": "腿/核心"},
    {"name": "三角式", "category": "瑜伽", "muscle": "腿/核心"},
    {"name": "树式", "category": "瑜伽", "muscle": "腿"},
    {"name": "船式", "category": "瑜伽", "muscle": "核心"},
    {"name": "桥式", "category": "瑜伽", "muscle": "臀"},
    {"name": "猫牛式", "category": "瑜伽", "muscle": "背"},
    {"name": "眼镜蛇式", "category": "瑜伽", "muscle": "背"},
    {"name": "婴儿式", "category": "瑜伽", "muscle": "背"},
    {"name": "坐立前屈", "category": "瑜伽", "muscle": "腿"},
    {"name": "鸽子式", "category": "瑜伽", "muscle": "臀"},
    {"name": "幻椅式", "category": "瑜伽", "muscle": "腿/臀"},
    {"name": "舞王式", "category": "瑜伽", "muscle": "全身"},
    # 力量（14）
    {"name": "深蹲", "category": "力量", "muscle": "腿/臀"},
    {"name": "硬拉", "category": "力量", "muscle": "腿/背"},
    {"name": "卧推", "category": "力量", "muscle": "胸"},
    {"name": "划船", "category": "力量", "muscle": "背"},
    {"name": "推举", "category": "力量", "muscle": "肩"},
    {"name": "引体向上", "category": "力量", "muscle": "背"},
    {"name": "俯卧撑", "category": "力量", "muscle": "胸"},
    {"name": "平板支撑", "category": "力量", "muscle": "核心"},
    {"name": "卷腹", "category": "力量", "muscle": "核心"},
    {"name": "臀桥", "category": "力量", "muscle": "臀"},
    {"name": "箭步蹲", "category": "力量", "muscle": "腿/臀"},
    {"name": "山羊挺身", "category": "力量", "muscle": "背"},
    {"name": "俄罗斯转体", "category": "力量", "muscle": "核心"},
    {"name": "侧平板支撑", "category": "力量", "muscle": "核心"},
    # 有氧（3）
    {"name": "开合跳", "category": "有氧", "muscle": "全身"},
    {"name": "波比跳", "category": "有氧", "muscle": "全身"},
    {"name": "高抬腿", "category": "有氧", "muscle": "腿"},
    # 拉伸（3）
    {"name": "靠墙静蹲", "category": "拉伸", "muscle": "腿"},
    {"name": "死虫式", "category": "拉伸", "muscle": "核心"},
    {"name": "鸟狗式", "category": "拉伸", "muscle": "背/核心"},
]

CATEGORIES = ["瑜伽", "力量", "有氧", "拉伸"]
