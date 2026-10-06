# -*- coding: utf-8 -*-
"""数据模型：用户、客户、自定义字段、评估记录、训练计划、饮食方案、系统设置。"""
import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now():
    """统一的创建时间默认值。"""
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    """系统用户：馆主（owner）或教练（coach）。"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="coach")  # owner / coach
    name: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)

    clients: Mapped[list["Client"]] = relationship("Client", back_populates="coach")


class Client(Base):
    """客户档案：基本信息 + 训练目标，归属某位教练。"""
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    gender: Mapped[str] = mapped_column(String(8), default="")      # 男 / 女
    age: Mapped[int] = mapped_column(Integer, default=0)
    height_cm: Mapped[float] = mapped_column(Float, default=0)       # 身高（厘米）
    phone: Mapped[str] = mapped_column(String(32), default="")
    goal: Mapped[str] = mapped_column(String(32), default="减脂")   # 减脂/增肌/塑形/体态改善
    notes: Mapped[str] = mapped_column(Text, default="")
    coach_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    custom_values: Mapped[dict] = mapped_column(JSON, default=dict)  # 客户级自定义字段值
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)

    coach: Mapped["User"] = relationship("User", back_populates="clients")
    assessments: Mapped[list["Assessment"]] = relationship(
        "Assessment", back_populates="client", cascade="all, delete-orphan"
    )


class CustomFieldDef(Base):
    """馆主自定义字段定义：可作用于客户档案或评估记录。"""
    __tablename__ = "custom_field_defs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))                    # 字段名，如“腰臀比”
    field_type: Mapped[str] = mapped_column(String(16), default="text")  # text / number
    target: Mapped[str] = mapped_column(String(16), default="assessment")  # client / assessment


class Assessment(Base):
    """一次身体评估记录：身体成分 + 围度 + 健康指标 + 自定义字段值。"""
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    date: Mapped[str] = mapped_column(String(16), default="")        # 评估日期 YYYY-MM-DD

    # 身体成分
    weight_kg: Mapped[float] = mapped_column(Float, default=0)
    body_fat_pct: Mapped[float] = mapped_column(Float, default=0)    # 体脂率 %
    muscle_kg: Mapped[float] = mapped_column(Float, default=0)       # 肌肉量 kg
    bmi: Mapped[float] = mapped_column(Float, default=0)
    visceral_fat: Mapped[float] = mapped_column(Float, default=0)    # 内脏脂肪等级

    # 围度（厘米）
    chest_cm: Mapped[float] = mapped_column(Float, default=0)
    waist_cm: Mapped[float] = mapped_column(Float, default=0)
    hip_cm: Mapped[float] = mapped_column(Float, default=0)
    arm_cm: Mapped[float] = mapped_column(Float, default=0)         # 上臂围
    thigh_cm: Mapped[float] = mapped_column(Float, default=0)       # 大腿围

    # 健康指标
    resting_hr: Mapped[int] = mapped_column(Integer, default=0)     # 静息心率
    blood_pressure: Mapped[str] = mapped_column(String(16), default="")  # 如 120/80
    injuries: Mapped[str] = mapped_column(Text, default="")         # 伤病史/注意事项

    custom_values: Mapped[dict] = mapped_column(JSON, default=dict)  # 自定义字段值 {字段id: 值}
    photo_path: Mapped[str] = mapped_column(String(256), default="")  # 体测单照片路径
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)

    client: Mapped["Client"] = relationship("Client", back_populates="assessments")


class TrainingPlan(Base):
    """训练计划：按周编排，可由系统自动生成、教练手动调整。"""
    __tablename__ = "training_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    week_start: Mapped[str] = mapped_column(String(16), default="")  # 计划开始日期
    # days 结构：[{"day": "周一", "time": "19:00", "exercises": [{"name": "深蹲", "sets": 4, "reps": "12"}]}]
    days: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / archived
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class DietPlan(Base):
    """饮食方案：精确到每天三餐加餐，需教练确认。"""
    __tablename__ = "diet_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    date: Mapped[str] = mapped_column(String(16), default="")        # 方案日期
    # meals 结构：{"breakfast": ["燕麦50g", ...], "lunch": [...], "dinner": [...], "snack": [...]}
    meals: Mapped[dict] = mapped_column(JSON, default=dict)
    calories_target: Mapped[int] = mapped_column(Integer, default=0)
    protein_g: Mapped[float] = mapped_column(Float, default=0)
    fat_g: Mapped[float] = mapped_column(Float, default=0)
    carbs_g: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending / confirmed
    confirmed_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class Setting(Base):
    """系统设置：只存非密钥类配置（如接口地址、模型名）；密钥一律走环境变量。"""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(512), default="")
