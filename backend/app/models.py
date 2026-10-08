# -*- coding: utf-8 -*-
"""数据模型：用户、客户、自定义字段、评估记录、训练计划、饮食方案、系统设置。"""
import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now():
    """统一的创建时间默认值。"""
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    """系统用户：馆主（owner）、教练（coach）或客户（client）。"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="coach")  # owner / coach / client
    name: Mapped[str] = mapped_column(String(64), default="")
    # 客户角色账号关联的客户档案（教练/馆主账号为空）
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)  # 注销后置 False
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)

    clients: Mapped[list["Client"]] = relationship(
        "Client", back_populates="coach", foreign_keys="Client.coach_id")


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
    # 出勤率（0~1）：签到/爽约后自动更新，供训练计划调整参考
    attendance_rate: Mapped[float] = mapped_column(Float, default=0)
    # 未成年人标记：14 岁以下需监护人同意（合规）
    is_minor: Mapped[bool] = mapped_column(default=False)
    guardian_consent: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)

    coach: Mapped["User"] = relationship(
        "User", back_populates="clients", foreign_keys="Client.coach_id")
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
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending / ai_draft / confirmed
    source: Mapped[str] = mapped_column(String(8), default="coach")  # coach / ai
    confirmed_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class Setting(Base):
    """系统设置：只存非密钥类配置（如接口地址、模型名）；密钥一律走环境变量。"""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(512), default="")


class Course(Base):
    """课程：约课签到的课程表。"""
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128), default="")       # 如"流瑜伽·晚间班"
    course_type: Mapped[str] = mapped_column(String(32), default="")   # 瑜伽/普拉提/私教…
    coach_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    start_time: Mapped[str] = mapped_column(String(32), default="")    # YYYY-MM-DD HH:MM
    end_time: Mapped[str] = mapped_column(String(32), default="")
    location: Mapped[str] = mapped_column(String(64), default="")
    capacity: Mapped[int] = mapped_column(Integer, default=20)         # 人数上限
    # 已占座位数（已约+已签到，不含候补/取消/爽约）。预约走原子 UPDATE 抢座，
    # 避免"先计数后插入"的并发超卖；取消/爽约/候补转正时同步增减。
    booked_seats: Mapped[int] = mapped_column(Integer, default=0)
    checkin_code: Mapped[str] = mapped_column(String(16), default="")  # 签到二维码码值
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class Booking(Base):
    """预约记录：booked（已约）/ waitlist（候补）/ cancelled（取消）
    / checked_in（已签到）/ no_show（爽约）。"""
    __tablename__ = "bookings"
    # 防重复预约的兜底：同一客户对同一课程只能有一条"有效"预约。
    # 取消/爽约后可重新约，所以用部分唯一索引（WHERE status IN …）
    # 而不是普通唯一约束。SQLite 与 Postgres 都支持部分索引；
    # 应用层在 book_course 事务内另有检查，索引是防竞态穿透的最后一道。
    __table_args__ = (
        Index(
            "uq_booking_active", "course_id", "client_id", unique=True,
            sqlite_where=text("status IN ('booked','waitlist','checked_in')"),
            postgresql_where=text("status IN ('booked','waitlist','checked_in')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="booked")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class CheckIn(Base):
    """签到记录：二维码扫码或教练手动确认。"""
    __tablename__ = "checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    method: Mapped[str] = mapped_column(String(16), default="qr")  # qr / manual
    checked_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class Consent(Base):
    """用户同意记录：敏感个人信息需单独同意（合规）。"""
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)  # 记录操作人
    consent_type: Mapped[str] = mapped_column(String(32), default="sensitive_info")
    # sensitive_info（敏感信息处理）/ ai_processing（AI 功能处理）
    version: Mapped[str] = mapped_column(String(16), default="v1")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class AuditLog(Base):
    """审计日志：关键写操作留痕（合规）。"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=0)
    action: Mapped[str] = mapped_column(String(64), default="")       # 如 client.create
    target_type: Mapped[str] = mapped_column(String(32), default="")  # 如 client
    target_id: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class AiPlan(Base):
    """AI 套餐：门店级订阅的套餐配置（免费版/专业版/旗舰版）。

    价格先填占位 0，由馆主在设置页修改；features 为功能开关字典，
    如 {"extract": true, "ocr": false, ...}。
    """
    __tablename__ = "ai_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), default="")        # 免费版/专业版/旗舰版
    monthly_price: Mapped[float] = mapped_column(Float, default=0)   # 月价（元，占位）
    yearly_price: Mapped[float] = mapped_column(Float, default=0)    # 年价（元，占位）
    ocr_per_month: Mapped[int] = mapped_column(Integer, default=0)   # 每月 OCR 次数
    voice_minutes_per_month: Mapped[int] = mapped_column(Integer, default=0)  # 每月语音分钟数
    llm_calls_per_month: Mapped[int] = mapped_column(Integer, default=0)  # 每月模型调用次数
    features: Mapped[dict] = mapped_column(JSON, default=dict)       # 功能开关
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class AiSubscription(Base):
    """AI 订阅：以门店为单位（owner 级别），不是按客户。

    开通目前由工作人员后台手动创建（原型）；未来在线收款时改为
    支付回调确认后激活（见 routers/subscriptions.py 的 TODO）。
    """
    __tablename__ = "ai_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("ai_plans.id"), nullable=True)
    # trialing（试用中）/ active（有效）/ expired（过期）/ paused（暂停）
    status: Mapped[str] = mapped_column(String(16), default="active")
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)
    note: Mapped[str] = mapped_column(String(128), default="")  # 备注（如手动开通原因）
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)

    plan: Mapped["AiPlan"] = relationship("AiPlan")


class AiUsage(Base):
    """AI 调用用量统计：按用户/类型计数；voice 按分钟数记 amount。"""
    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # extract（自然语言录入）/ ocr（体测单识别）/ voice（语音转记录）
    # / plan_diet（生成训练/饮食建议）/ summary（客户总结）
    kind: Mapped[str] = mapped_column(String(32), default="extract")
    amount: Mapped[float] = mapped_column(Float, default=1)  # 用量单位数（voice=分钟，其余=1）
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class WxBinding(Base):
    """微信绑定：一个微信 openid 绑定一个系统账号，用于 wx.login 免密登录。"""
    __tablename__ = "wx_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    openid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class Notification(Base):
    """站内通知：AI 饮食、预约/候补/签到等事件的推送（一期站内，二期微信订阅消息）。"""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # 接收人
    type: Mapped[str] = mapped_column(String(32), default="")  # diet_ai_ready / diet_confirmed / booking_created / booking_promoted / checkin / system
    title: Mapped[str] = mapped_column(String(128), default="")
    body: Mapped[str] = mapped_column(String(512), default="")
    ref_type: Mapped[str] = mapped_column(String(32), default="")
    ref_id: Mapped[int] = mapped_column(Integer, default=0)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)


class DailyCheckin(Base):
    """每日打卡：训练/饮食二选一，每天每种一次。照片打卡走上传接口。"""
    __tablename__ = "daily_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    date: Mapped[str] = mapped_column(String(16), default="")          # YYYY-MM-DD
    kind: Mapped[str] = mapped_column(String(16), default="training")  # training / diet
    note: Mapped[str] = mapped_column(Text, default="")
    photo_path: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now)

    __table_args__ = (
        UniqueConstraint("client_id", "date", "kind", name="uq_checkin_client_date_kind"),
    )
