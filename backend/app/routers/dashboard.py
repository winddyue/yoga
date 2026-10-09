# -*- coding: utf-8 -*-
"""经营概况路由：按角色返回汇总数据。

- /api/dashboard：兼容旧版，仅工作人员（馆主看全馆，教练看自己）
- /api/dashboard/me/summary：客户看自己的进展
- /api/dashboard/coach/overview：教练看名下客户状态灯 + 待办
- /api/dashboard/owner/overview：馆主看经营数据
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models
from ..database import get_db
from ..services import ai_gate as ai_gate_service

router = APIRouter(prefix="/api/dashboard", tags=["经营概况"])


@router.get("")
def overview(db: Session = Depends(get_db),
             user: models.User = Depends(auth_lib.require_staff)):
    """经营概况：馆主看全馆，教练看自己的客户。

    客户角色不允许访问（前端应走 /api/dashboard/me/summary）。
    """
    q = db.query(models.Client)
    if user.role != "owner":
        q = q.filter(models.Client.coach_id == user.id)
    clients = q.all()
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    recent_assessments = (db.query(models.Assessment)
                          .filter(models.Assessment.client_id.in_([c.id for c in clients] or [0]),
                                   models.Assessment.date >= week_ago).count())
    pending_diets = (db.query(models.DietPlan)
                     .filter(models.DietPlan.client_id.in_([c.id for c in clients] or [0]),
                              models.DietPlan.status == "pending").count())
    return {
        "client_count": len(clients),
        "coach_count": db.query(models.User).filter(models.User.role == "coach").count(),
        "week_assessments": recent_assessments,
        "pending_diets": pending_diets,  # 待确认的饮食方案数
    }


def _latest_assessment_days(db: Session, client: models.Client):
    """距上次评估天数；无评估或日期非法返回 None。"""
    latest = (db.query(models.Assessment)
              .filter(models.Assessment.client_id == client.id)
              .order_by(models.Assessment.date.desc()).first())
    if not latest or not latest.date:
        return None
    try:
        return (datetime.now() - datetime.strptime(latest.date, "%Y-%m-%d")).days
    except (ValueError, TypeError):
        return None


def _action_for(client: models.Client, status: str) -> str:
    """按状态灯推导建议动作。

    注：red ⟺ 无评估或超 60 天未评估，因此"出勤低"优先于"安排复测"判断，
    否则第二条规则永远不可达。
    """
    if status == "red":
        if (client.attendance_rate or 0) < 0.5:
            return "出勤低，需跟进"
        return "安排复测"
    if status == "yellow":
        return "提醒复测/关注出勤"
    return ""


def _client_status(db: Session, client: models.Client) -> str:
    """客户状态灯：红（长期未评估/出勤差）/ 黄（30 天未复测）/ 绿（正常）。"""
    latest = (db.query(models.Assessment)
              .filter(models.Assessment.client_id == client.id)
              .order_by(models.Assessment.date.desc()).first())
    if not latest:
        return "red"
    try:
        last_date = datetime.strptime(latest.date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return "yellow"
    days = (datetime.now() - last_date).days
    if days > 60:
        return "red"
    if days > 30:
        return "yellow"
    if (client.attendance_rate or 0) < 0.5:
        return "yellow"
    return "green"


@router.get("/me/summary")
def my_summary(db: Session = Depends(get_db),
               user: models.User = Depends(auth_lib.get_current_user)):
    """客户看自己的进展：出勤率、饮食确认数、体重变化、目标。"""
    client = auth_lib.get_own_client(db, user)
    rows = (db.query(models.Assessment)
            .filter(models.Assessment.client_id == client.id)
            .order_by(models.Assessment.date.asc()).all())
    weights = [r.weight_kg for r in rows if r.weight_kg]
    weight_change = round(weights[-1] - weights[0], 1) if len(weights) >= 2 else 0
    diet_done = (db.query(models.DietPlan)
                 .filter(models.DietPlan.client_id == client.id,
                         models.DietPlan.status == "confirmed").count())
    bookings = (db.query(models.Booking)
                .filter(models.Booking.client_id == client.id,
                        models.Booking.status.in_(("booked", "waitlist"))).count())
    return {
        "name": client.name, "goal": client.goal,
        "attendance_rate": client.attendance_rate or 0,
        "weight_change": weight_change,
        "assessment_count": len(rows),
        "diet_confirmed": diet_done,
        "upcoming_bookings": bookings,
        "status": _client_status(db, client),
    }


@router.get("/me/monthly")
def my_monthly(db: Session = Depends(get_db),
               user: models.User = Depends(auth_lib.get_current_user)):
    """本月总结（SparkyFitness 式长期报告的月度版）：评估次数、体重/体脂变化、本月签到、一句话总结。"""
    client = auth_lib.get_own_client(db, user)
    now = datetime.now()
    month = now.strftime("%Y-%m")
    month_start = datetime(now.year, now.month, 1)
    rows = (db.query(models.Assessment)
            .filter(models.Assessment.client_id == client.id,
                    models.Assessment.date.like(f"{month}%"))
            .order_by(models.Assessment.date.asc()).all())
    weights = [r.weight_kg for r in rows if r.weight_kg and r.weight_kg > 0]
    fats = [r.body_fat_pct for r in rows if r.body_fat_pct and r.body_fat_pct > 0]
    weight_change = round(weights[-1] - weights[0], 1) if len(weights) >= 2 else None
    body_fat_change = round(fats[-1] - fats[0], 1) if len(fats) >= 2 else None
    checkin_count = (db.query(models.CheckIn)
                     .filter(models.CheckIn.client_id == client.id,
                             models.CheckIn.checked_at >= month_start).count())
    m = now.month
    if not rows:
        text = "先记录一次体测吧"
    else:
        parts = [f"{m}月你记录了{len(rows)}次体测"]
        if weight_change is None:
            parts.append("多测一次就能看到体重变化趋势")
        else:
            d = "下降" if weight_change < 0 else ("上升" if weight_change > 0 else "持平")
            parts.append(f"体重{d}{abs(weight_change)}kg")
        if body_fat_change is not None and body_fat_change != 0:
            d = "下降" if body_fat_change < 0 else "上升"
            parts.append(f"体脂{d}{abs(body_fat_change)}%")
        parts.append(f"本月出勤{checkin_count}次")
        tail = "继续保持！" if (weight_change or 0) <= 0 else "别灰心，坚持就是胜利"
        text = "，".join(parts) + "。" + tail
    return {
        "month": month, "assess_count": len(rows),
        "weight_change": weight_change, "body_fat_change": body_fat_change,
        "checkin_count": checkin_count, "text": text,
    }


def _monthly_attendance(db: Session, client_id: int):
    """近 6 个月出勤：只计已发生课程（课程 start_time <= now 的预约）。

    attended=checked_in 数，total=attended+no_show。
    """
    now = datetime.now()
    now_s = now.strftime("%Y-%m-%d %H:%M")
    months, y, m = [], now.year, now.month
    for _ in range(6):
        months.append("%04d-%02d" % (y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    months.reverse()
    buckets = {k: [0, 0] for k in months}  # month -> [attended, total]
    rows = (db.query(models.Booking, models.Course.start_time)
            .join(models.Course, models.Booking.course_id == models.Course.id)
            .filter(models.Booking.client_id == client_id,
                    models.Booking.status.in_(("checked_in", "no_show"))).all())
    for b, start_time in rows:
        if not start_time or start_time > now_s:
            continue  # 未发生的课程不计
        mk = start_time[:7]
        if mk not in buckets:
            continue
        buckets[mk][1] += 1
        if b.status == "checked_in":
            buckets[mk][0] += 1
    return [{"month": k, "attended": a, "total": t,
             "rate": round(a / t, 3) if t else 0}
            for k, (a, t) in buckets.items()]


@router.get("/me/charts")
def my_charts(db: Session = Depends(get_db),
              user: models.User = Depends(auth_lib.get_current_user)):
    """客户图表数据包：趋势序列、相对首次评估的变化、近 6 个月出勤。"""
    client = auth_lib.get_own_client(db, user)
    rows = (db.query(models.Assessment)
            .filter(models.Assessment.client_id == client.id)
            .order_by(models.Assessment.date.asc()).all())
    trends = {
        "dates": [r.date for r in rows],
        "weight": [r.weight_kg for r in rows],
        "body_fat": [r.body_fat_pct for r in rows],
        "waist": [r.waist_cm for r in rows],
        "hip": [r.hip_cm for r in rows],
    }

    def _change(vals):
        v = [x for x in vals if x and x > 0]
        return round(v[-1] - v[0], 1) if len(v) >= 2 else 0

    changes = {"weight": _change(trends["weight"]),
               "body_fat": _change(trends["body_fat"]),
               "waist": _change(trends["waist"])}
    return {"trends": trends, "changes": changes,
            "monthly_attendance": _monthly_attendance(db, client.id)}


@router.get("/coach/overview")
def coach_overview(db: Session = Depends(get_db),
                   user: models.User = Depends(auth_lib.require_staff)):
    """教练工作台：名下客户状态灯 + 待办（待确认饮食、到期复测）。"""
    q = db.query(models.Client)
    if user.role != "owner":
        q = q.filter(models.Client.coach_id == user.id)
    clients = q.all()
    cids = [c.id for c in clients] or [0]
    pending_diets = (db.query(models.DietPlan)
                     .filter(models.DietPlan.client_id.in_(cids),
                             models.DietPlan.status == "pending").count())
    due = sum(1 for c in clients if _client_status(db, c) in ("red", "yellow"))
    # 近 30 天活跃客户集合：供前端「近30天活跃」下钻过滤（口径见 _recent_active_cids）
    recent_cids = _recent_active_cids(db, 30)
    items = []
    for c in clients:
        st = _client_status(db, c)
        items.append({"id": c.id, "name": c.name, "goal": c.goal,
                      "attendance_rate": c.attendance_rate or 0,
                      "status": st,
                      "days_since_assessment": _latest_assessment_days(db, c),
                      "action": _action_for(c, st),
                      "recent_active": c.id in recent_cids,
                      "created_at": c.created_at.strftime("%Y-%m-%d")
                      if c.created_at else ""})
    return {
        "clients": items,
        "todos": {"pending_diets": pending_diets, "due_reassess": due},
    }


def _recent_active_cids(db: Session, days: int = 30) -> set:
    """近 N 天「活跃」客户：有预约 / 评估 / 打卡任一记录的客户。

    不能只看预约——课程预约功能暂隐后该指标会恒为 0；把评估与打卡一并纳入，
    指标才会随客户真实活动变化，首页「近30天活跃」的下钻也有内容。
    """
    since_dt = datetime.now() - timedelta(days=days)
    since_day = since_dt.date().isoformat()
    cids = set()
    cids |= {r[0] for r in db.query(models.Booking.client_id)
             .filter(models.Booking.created_at >= since_dt).all()}
    cids |= {r[0] for r in db.query(models.Assessment.client_id)
             .filter(models.Assessment.date >= since_day).all()}
    cids |= {r[0] for r in db.query(models.DailyCheckin.client_id)
             .filter(models.DailyCheckin.date >= since_day).all()}
    return cids


@router.get("/owner/overview")
def owner_overview(db: Session = Depends(get_db),
                   _: models.User = Depends(auth_lib.require_owner)):
    """馆主经营页：新增/活跃客户、课程量、教练业绩、订阅统计。"""
    month_ago = datetime.now() - timedelta(days=30)
    new_clients = (db.query(models.Client)
                   .filter(models.Client.created_at >= month_ago).count())
    total_clients = db.query(models.Client).count()
    active_cids = _recent_active_cids(db, 30)
    course_count = db.query(models.Course).count()
    booking_count = (db.query(models.Booking)
                     .filter(models.Booking.created_at >= month_ago).count())
    checkins = (db.query(models.Booking)
                .filter(models.Booking.status == "checked_in").count())
    # 教练业绩：名下客户数 + 课程数 + 签到数
    coaches = db.query(models.User).filter(models.User.role == "coach").all()
    perf = []
    for co in coaches:
        cids = [c.id for c in co.clients]
        perf.append({
            "coach_id": co.id, "name": co.name or co.username,
            "clients": len(co.clients),
            "courses": db.query(models.Course).filter(
                models.Course.coach_id == co.id).count(),
            "checkins": (db.query(models.CheckIn)
                         .filter(models.CheckIn.client_id.in_(cids)).count()
                         if cids else 0),
        })
    active_subs = (db.query(models.AiSubscription)
                   .filter(models.AiSubscription.status.in_(("trialing", "active"))).count())
    ai_calls = db.query(func.count(models.AiUsage.id)).scalar() or 0
    ai_summary = ai_gate_service.subscription_summary(db)
    return {
        "new_clients_30d": new_clients, "total_clients": total_clients,
        "active_clients_30d": len(active_cids),
        "course_count": course_count, "bookings_30d": booking_count,
        "total_checkins": checkins, "coach_perf": perf,
        "active_subscriptions": active_subs, "ai_calls": ai_calls,
        "ai_subscription": ai_summary.get("subscription"),
        "ai_quotas": ai_summary.get("quotas", {}),
    }
