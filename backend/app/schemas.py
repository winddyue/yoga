# -*- coding: utf-8 -*-
"""Pydantic 数据校验模型：请求入参 / 响应出参。"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


# ---------- 通用 ----------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    name: str


class LoginIn(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "coach"  # owner / coach
    name: str = ""


# ---------- 客户 ----------
class ClientIn(BaseModel):
    name: str
    gender: str = ""
    age: int = 0
    height_cm: float = 0
    phone: str = ""
    goal: str = "减脂"
    notes: str = ""
    coach_id: Optional[int] = None
    custom_values: Dict[str, Any] = {}


class ClientOut(ClientIn):
    id: int
    custom_values: Dict[str, Any] = {}


# ---------- 自定义字段 ----------
class CustomFieldIn(BaseModel):
    name: str
    field_type: str = "text"       # text / number
    target: str = "assessment"    # client / assessment


class CustomFieldOut(CustomFieldIn):
    id: int


# ---------- 评估 ----------
class AssessmentIn(BaseModel):
    date: str = ""
    weight_kg: float = 0
    body_fat_pct: float = 0
    muscle_kg: float = 0
    bmi: float = 0
    visceral_fat: float = 0
    chest_cm: float = 0
    waist_cm: float = 0
    hip_cm: float = 0
    arm_cm: float = 0
    thigh_cm: float = 0
    resting_hr: int = 0
    blood_pressure: str = ""
    injuries: str = ""
    custom_values: Dict[str, Any] = {}
    photo_path: str = ""


class AssessmentOut(AssessmentIn):
    id: int
    client_id: int


# ---------- 训练计划 ----------
class ExerciseIn(BaseModel):
    name: str
    sets: int = 3
    reps: str = "12"


class PlanDayIn(BaseModel):
    day: str
    time: str = ""
    exercises: List[ExerciseIn] = []


class TrainingPlanIn(BaseModel):
    week_start: str = ""
    days: List[PlanDayIn] = []


class TrainingPlanOut(BaseModel):
    id: int
    client_id: int
    week_start: str
    days: List[Dict[str, Any]]
    status: str


# ---------- 饮食方案 ----------
class DietPlanIn(BaseModel):
    date: str = ""
    meals: Dict[str, List[str]] = {}
    calories_target: int = 0
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0


class DietPlanOut(DietPlanIn):
    id: int
    client_id: int
    status: str


class DietGenerateIn(BaseModel):
    date: str = ""
    activity_level: str = "moderate"  # light / moderate / active


# ---------- 设置 ----------
class SettingsOut(BaseModel):
    ocr_api_url: str = ""
    ai_api_url: str = ""
    ai_model: str = ""
    ocr_configured: bool = False  # 密钥是否已配置（只返回状态，不返回明文）
    ai_configured: bool = False


class SettingsIn(BaseModel):
    ocr_api_url: Optional[str] = None
    ai_api_url: Optional[str] = None
    ai_model: Optional[str] = None
