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
    role: str = "coach"  # owner / coach / client
    name: str = ""
    client_id: Optional[int] = None  # 客户角色账号绑定的客户档案


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
    is_minor: bool = False
    guardian_consent: bool = False


class ClientOut(ClientIn):
    id: int
    custom_values: Dict[str, Any] = {}
    attendance_rate: float = 0


class ClientSelfOut(BaseModel):
    """客户角色看到的自己档案：不含教练内部备注等敏感字段（字段级权限）。"""
    id: int
    name: str
    gender: str = ""
    age: int = 0
    height_cm: float = 0
    phone: str = ""
    goal: str = "减脂"
    coach_id: Optional[int] = None
    custom_values: Dict[str, Any] = {}
    attendance_rate: float = 0
    is_minor: bool = False


class ClientSelfUpdate(BaseModel):
    """客户可自行更正的基础信息（用户权利：更正权）。"""
    name: Optional[str] = None
    phone: Optional[str] = None
    height_cm: Optional[float] = None


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
    asr_api_url: str = ""
    ai_enabled: bool = False
    ai_price_monthly: float = 0
    ai_price_yearly: float = 0
    ocr_configured: bool = False  # 密钥是否已配置（只返回状态，不返回明文）
    ai_configured: bool = False
    asr_configured: bool = False


class SettingsIn(BaseModel):
    ocr_api_url: Optional[str] = None
    ai_api_url: Optional[str] = None
    ai_model: Optional[str] = None
    asr_api_url: Optional[str] = None
    ai_enabled: Optional[bool] = None
    ai_price_monthly: Optional[float] = None
    ai_price_yearly: Optional[float] = None


# ---------- 约课签到 ----------
class CourseIn(BaseModel):
    title: str
    course_type: str = ""
    coach_id: Optional[int] = None
    start_time: str = ""   # YYYY-MM-DD HH:MM
    end_time: str = ""
    location: str = ""
    capacity: int = 20


class CourseOut(CourseIn):
    id: int
    checkin_code: str = ""
    booked_count: int = 0  # 当前已约人数（不含候补/取消）


class BookingOut(BaseModel):
    id: int
    course_id: int
    client_id: int
    client_name: str = ""
    status: str


class CheckInIn(BaseModel):
    client_id: Optional[int] = None  # 教练手动签到时指定；客户扫码时为空
    code: Optional[str] = None       # 客户扫码签到的码值


# ---------- 智能录入 ----------
class ExtractIn(BaseModel):
    text: str  # 自由文本，如"身高175体重80体脂25"


class ExtractOut(BaseModel):
    fields: Dict[str, Any]  # 抽取出的评估字段（待确认，未入库）
    raw_text: str


class IntakeConfirmIn(BaseModel):
    client_id: int
    fields: Dict[str, Any]  # 确认后的字段，写入评估记录


# ---------- AI 订阅 ----------
class SubscriptionIn(BaseModel):
    client_id: int
    plan: str = "monthly"  # monthly / yearly


class SubscriptionOut(BaseModel):
    id: int
    client_id: int
    plan: str
    started_at: Any = None
    expires_at: Any = None
    status: str


class PricingOut(BaseModel):
    ai_enabled: bool = False
    ai_price_monthly: float = 0
    ai_price_yearly: float = 0


# ---------- 同意记录 ----------
class ConsentIn(BaseModel):
    client_id: int
    consent_type: str = "sensitive_info"  # sensitive_info / ai_processing
    version: str = "v1"


class ConsentOut(BaseModel):
    id: int
    client_id: Optional[int] = None
    consent_type: str
    version: str
