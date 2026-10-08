# -*- coding: utf-8 -*-
"""约课签到：课程表、预约/取消（含候补）、二维码签到、教练手动确认、爽约标记。
出勤率自动写回客户档案，供训练计划调整参考。"""
import datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..services import audit as audit_service

router = APIRouter(prefix="/api", tags=["约课签到"])

# 预约状态
ST_BOOKED = "booked"
ST_WAITLIST = "waitlist"
ST_CANCELLED = "cancelled"
ST_CHECKED_IN = "checked_in"
ST_NO_SHOW = "no_show"
ACTIVE_BOOKING = (ST_BOOKED, ST_CHECKED_IN)

# 课程时间字符串的两种格式："2026-10-07 07:00"（v2 起默认）/ ISO "2026-10-07T07:00:00"
_TIME_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S")


def _parse_course_time(value: str):
    """课程时间字符串 -> naive datetime；解析失败返回 None（不阻断签到）。"""
    if not value:
        return None
    for fmt in _TIME_FORMATS:
        try:
            return datetime.datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _booked_count(db: Session, course_id: int) -> int:
    """当前有效预约人数（已约+已签到，不含候补/取消/爽约）。仅用于展示；
    并发名额校验走 courses.booked_seats 原子计数（见 _take_seat）。"""
    return (db.query(models.Booking)
            .filter(models.Booking.course_id == course_id,
                    models.Booking.status.in_((ST_BOOKED, ST_CHECKED_IN))).count())


def _take_seat(db: Session, course_id: int) -> bool:
    """原子抢座：booked_seats < capacity 时 +1，返回是否抢到。

    单条 UPDATE … WHERE …，在 SQLite 与 Postgres 下都是原子执行，
    不存在"先查名额再插入"的竞态窗口。这是防超卖的唯一关口。
    """
    result = db.execute(
        update(models.Course)
        .where(models.Course.id == course_id,
               models.Course.booked_seats < models.Course.capacity)
        .values(booked_seats=models.Course.booked_seats + 1))
    return result.rowcount == 1


def _adjust_seats(db: Session, course_id: int, delta: int) -> None:
    """无条件增减座位数（释放座位 / 人工放行时的配额同步）。

    单条原子 UPDATE；delta 为负数时不会把计数器减到 0 以下。
    """
    stmt = (update(models.Course)
            .where(models.Course.id == course_id)
            .values(booked_seats=models.Course.booked_seats + delta))
    if delta < 0:
        stmt = stmt.where(models.Course.booked_seats >= -delta)
    db.execute(stmt)


def _promote_waitlist(db: Session, course_id: int) -> int | None:
    """原子转正：把最早的一条候补翻成已约，返回其 client_id。

    转正只改预约状态、不动座位计数器（座位从取消者手里直接过户）。
    WHERE status='waitlist' 保证两个并发取消不会把同一条候补转正两次。
    """
    first = (db.query(models.Booking.id, models.Booking.client_id)
             .filter(models.Booking.course_id == course_id,
                     models.Booking.status == ST_WAITLIST)
             .order_by(models.Booking.created_at.asc()).first())
    if not first:
        return None
    result = db.execute(
        update(models.Booking)
        .where(models.Booking.id == first.id,
               models.Booking.status == ST_WAITLIST)
        .values(status=ST_BOOKED))
    return first.client_id if result.rowcount == 1 else None


def _course_out(db: Session, course: models.Course,
                user: models.User | None) -> dict:
    """课程输出：签到码只给工作人员（馆主/教练），客户与游客不可见。"""
    out = {c.name: getattr(course, c.name)
           for c in course.__table__.columns if c.name != "checkin_code"}
    if user is not None and user.role in ("owner", "coach"):
        out["checkin_code"] = course.checkin_code
    out["booked_count"] = _booked_count(db, course.id)
    return out


def update_attendance(db: Session, client_id: int):
    """重算出勤率并写回客户档案：签到数 /（签到数 + 爽约数）。"""
    checked = (db.query(models.Booking)
               .filter(models.Booking.client_id == client_id,
                       models.Booking.status == ST_CHECKED_IN).count())
    noshow = (db.query(models.Booking)
              .filter(models.Booking.client_id == client_id,
                      models.Booking.status == ST_NO_SHOW).count())
    total = checked + noshow
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if client:
        client.attendance_rate = round(checked / total, 3) if total else 0.0
        db.commit()


@router.post("/courses", response_model=schemas.CourseOut,
            response_model_exclude_unset=True)
def create_course(data: schemas.CourseIn,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.require_staff)):
    """新建课程（馆主/教练）：自动生成签到二维码码值。"""
    coach_id = data.coach_id or (user.id if user.role == "coach" else None)
    course = models.Course(
        **data.model_dump(exclude={"coach_id"}),
        coach_id=coach_id,
        checkin_code=secrets.token_hex(4),  # 8 位十六进制码值
        created_by=user.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    audit_service.log(db, user.id, "course.create", "course", course.id)
    return _course_out(db, course, user)


@router.get("/courses", response_model=list[schemas.CourseOut],
            response_model_exclude_unset=True)
def list_courses(db: Session = Depends(get_db),
                 user: models.User | None = Depends(auth_lib.get_optional_user)):
    """课程列表（按开始时间倒序）。游客可浏览，签到码不下发。"""
    courses = db.query(models.Course).order_by(models.Course.start_time.desc()).all()
    return [_course_out(db, c, user) for c in courses]


@router.get("/courses/{course_id}", response_model=schemas.CourseOut,
            response_model_exclude_unset=True)
def get_course(course_id: int,
               db: Session = Depends(get_db),
               user: models.User | None = Depends(auth_lib.get_optional_user)):
    """课程详情。游客可浏览，签到码不下发。"""
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    return _course_out(db, course, user)


def _resolve_client(db: Session, user: models.User,
                    client_id: int | None) -> models.Client:
    """确定预约主体：客户只能给自己约，工作人员可代客户约。"""
    if user.role == "client":
        return auth_lib.get_own_client(db, user)
    if not client_id:
        raise HTTPException(status_code=400, detail="需指定客户")
    return auth_lib.client_visible_to(db, user, client_id)


@router.post("/courses/{course_id}/book", response_model=schemas.BookingOut)
def book_course(course_id: int, body: dict | None = None,
                db: Session = Depends(get_db),
                user: models.User = Depends(auth_lib.get_current_user)):
    """预约课程：原子抢座，满员自动进候补名单。

    并发安全：名额校验是单条 UPDATE … WHERE booked_seats < capacity
    （_take_seat），SQLite / Postgres 下都原子，不存在"先查后插"的
    超卖窗口；同一客户的重复预约另有应用层检查 + bookings 表部分
    唯一索引兜底（uq_booking_active），穿透时转为友好的 400。
    """
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    client = _resolve_client(db, user, (body or {}).get("client_id"))
    dup = (db.query(models.Booking)
           .filter(models.Booking.course_id == course_id,
                   models.Booking.client_id == client.id,
                   models.Booking.status.in_((ST_BOOKED, ST_WAITLIST, ST_CHECKED_IN))).first())
    if dup:
        raise HTTPException(status_code=400, detail="已预约该课程，无需重复预约")
    status = ST_BOOKED if _take_seat(db, course_id) else ST_WAITLIST
    booking = models.Booking(course_id=course_id, client_id=client.id, status=status)
    db.add(booking)
    try:
        db.commit()  # 抢座与插入同属一个事务：索引冲突回滚时座位一并归还
    except IntegrityError:
        # 极端竞态下应用层检查被穿透，部分唯一索引 uq_booking_active
        # 兜底，转为友好的 400
        db.rollback()
        raise HTTPException(status_code=400, detail="已预约该课程，无需重复预约")
    db.refresh(booking)
    audit_service.log(db, user.id, "booking.create", "booking", booking.id)
    return {"id": booking.id, "course_id": course_id, "client_id": client.id,
            "client_name": client.name, "status": booking.status}


@router.post("/courses/{course_id}/cancel")
def cancel_booking(course_id: int, body: dict | None = None,
                   db: Session = Depends(get_db),
                   user: models.User = Depends(auth_lib.get_current_user)):
    """取消预约：候补名单第一位自动转正。

    座位交接：取消的是已约座位时，优先把座位过户给最早候补
    （_promote_waitlist 原子转正）；没有候补才释放座位。
    取消候补本身不占座位，无需调整计数器。
    """
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    client = _resolve_client(db, user, (body or {}).get("client_id"))
    booking = (db.query(models.Booking)
               .filter(models.Booking.course_id == course_id,
                       models.Booking.client_id == client.id,
                       models.Booking.status.in_((ST_BOOKED, ST_WAITLIST))).first())
    if not booking:
        raise HTTPException(status_code=404, detail="没有可取消的预约")
    was_booked = (booking.status == ST_BOOKED)
    booking.status = ST_CANCELLED
    db.flush()  # session 为 autoflush=False，需手动刷入
    promoted = None
    if was_booked:
        promoted = _promote_waitlist(db, course_id)
        if promoted is None:
            _adjust_seats(db, course_id, -1)
    db.commit()
    audit_service.log(db, user.id, "booking.cancel", "booking", booking.id)
    return {"ok": True, "promoted_client_id": promoted}


@router.get("/courses/{course_id}/roster", response_model=list[schemas.BookingOut])
def course_roster(course_id: int,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.require_staff)):
    """课程名单（含候补/签到状态，仅工作人员）。"""
    rows = (db.query(models.Booking, models.Client.name)
            .join(models.Client, models.Client.id == models.Booking.client_id)
            .filter(models.Booking.course_id == course_id)
            .order_by(models.Booking.created_at.asc()).all())
    return [{"id": b.id, "course_id": b.course_id, "client_id": b.client_id,
             "client_name": name, "status": b.status} for b, name in rows]


@router.post("/courses/{course_id}/checkin")
def checkin(course_id: int, data: schemas.CheckInIn,
            db: Session = Depends(get_db),
            user: models.User = Depends(auth_lib.get_current_user)):
    """签到：客户扫码（校验码值）或教练手动确认。"""
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    if user.role == "client":
        client = auth_lib.get_own_client(db, user)
        if not data.code or data.code != course.checkin_code:
            raise HTTPException(status_code=400, detail="签到码无效")
        # 签到时间窗：客户自助扫码仅允许开课前 30 分钟 ~ 开课后 60 分钟
        #（窗口大小可配置）；教练手动补签不受此限制
        start = _parse_course_time(course.start_time)
        if start is not None:
            now = datetime.datetime.now()
            opens = start - datetime.timedelta(minutes=settings.CHECKIN_OPEN_MIN)
            closes = start + datetime.timedelta(minutes=settings.CHECKIN_CLOSE_MIN)
            if now < opens:
                raise HTTPException(
                    status_code=400,
                    detail=f"还未到签到时间，开课前 {settings.CHECKIN_OPEN_MIN} 分钟开放")
            if now > closes:
                raise HTTPException(
                    status_code=400,
                    detail="签到时间已结束，请联系教练补签")
        method = "qr"
    else:
        if not data.client_id:
            raise HTTPException(status_code=400, detail="需指定客户")
        client = auth_lib.client_visible_to(db, user, data.client_id)
        method = "manual"
    booking = (db.query(models.Booking)
               .filter(models.Booking.course_id == course_id,
                       models.Booking.client_id == client.id,
                       models.Booking.status.in_(
                           (ST_BOOKED, ST_WAITLIST, ST_CHECKED_IN))).first())
    if not booking:
        raise HTTPException(status_code=400, detail="该客户未预约本课程")
    # 已签到时给出准确提示，避免重复扫码被误报成"未预约"
    if booking.status == ST_CHECKED_IN:
        raise HTTPException(status_code=400, detail="您已签到，无需重复签到")
    if booking.status == ST_WAITLIST:
        # 候补直接签到 = 教练/馆主人工放行：同步占用一个座位。
        # 计数器如实记录（可能短暂超出 capacity），后续预约关口
        # 仍以 booked_seats < capacity 为准，不会因此超卖。
        _adjust_seats(db, course_id, 1)
    booking.status = ST_CHECKED_IN
    db.add(models.CheckIn(course_id=course_id, client_id=client.id, method=method))
    db.commit()
    update_attendance(db, client.id)
    audit_service.log(db, user.id, "booking.checkin", "booking", booking.id)
    return {"ok": True, "method": method}


@router.get("/courses/{course_id}/qrcode")
def course_qrcode(course_id: int,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.require_staff)):
    """签到二维码（仅工作人员）：教练出示给客户扫。

    二维码内容为 "yoga:checkin:课程id:签到码"，客户端扫码后调签到接口。
    返回 PNG 的 base64（小程序 image 标签无法带 Authorization 头，
    由页面用 wx.request 取回后以 data URL 渲染）。
    """
    import base64
    import io

    import qrcode

    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    content = f"yoga:checkin:{course.id}:{course.checkin_code}"
    img = qrcode.make(content)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return {"content": content, "png_base64": base64.b64encode(buf.getvalue()).decode()}


@router.post("/courses/{course_id}/mark-noshow")
def mark_noshow(course_id: int,
                db: Session = Depends(get_db),
                user: models.User = Depends(auth_lib.require_staff)):
    """爽约标记：课程结束后，未签到的已预约记为爽约（仅工作人员）。"""
    rows = (db.query(models.Booking)
            .filter(models.Booking.course_id == course_id,
                    models.Booking.status == ST_BOOKED).all())
    for b in rows:
        b.status = ST_NO_SHOW
    if rows:
        _adjust_seats(db, course_id, -len(rows))  # 释放座位
    db.commit()
    for b in rows:
        update_attendance(db, b.client_id)
    audit_service.log(db, user.id, "booking.noshow", "course", course_id)
    return {"ok": True, "marked": len(rows)}


@router.get("/bookings/mine", response_model=list[schemas.MyBookingOut])
def my_bookings(db: Session = Depends(get_db),
                user: models.User = Depends(auth_lib.get_current_user)):
    """客户查看自己的约课/签到记录。附带课程信息，前端无需逐门课再查。"""
    client = auth_lib.get_own_client(db, user)
    rows = (db.query(models.Booking)
            .filter(models.Booking.client_id == client.id)
            .order_by(models.Booking.created_at.desc()).all())
    out = []
    for b in rows:
        course = db.query(models.Course).filter(models.Course.id == b.course_id).first()
        out.append({
            "id": b.id, "course_id": b.course_id, "client_id": b.client_id,
            "client_name": client.name, "status": b.status,
            "course_title": course.title if course else "（课程已删除）",
            "start_time": course.start_time if course else "",
            "end_time": course.end_time if course else "",
            "location": course.location if course else "",
        })
    return out
