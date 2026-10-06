# -*- coding: utf-8 -*-
"""约课签到：课程表、预约/取消（含候补）、二维码签到、教练手动确认、爽约标记。
出勤率自动写回客户档案，供训练计划调整参考。"""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
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


def _booked_count(db: Session, course_id: int) -> int:
    """当前有效预约人数（已约+已签到，不含候补/取消/爽约）。"""
    return (db.query(models.Booking)
            .filter(models.Booking.course_id == course_id,
                    models.Booking.status.in_((ST_BOOKED, ST_CHECKED_IN))).count())


def _course_out(db: Session, course: models.Course) -> dict:
    return {**{c.name: getattr(course, c.name)
               for c in course.__table__.columns if c.name != "checkin_code"},
            "checkin_code": course.checkin_code,
            "booked_count": _booked_count(db, course.id)}


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


@router.post("/courses", response_model=schemas.CourseOut)
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
    return _course_out(db, course)


@router.get("/courses", response_model=list[schemas.CourseOut])
def list_courses(db: Session = Depends(get_db),
                 user: models.User = Depends(auth_lib.get_current_user)):
    """课程列表（按开始时间倒序）。"""
    courses = db.query(models.Course).order_by(models.Course.start_time.desc()).all()
    return [_course_out(db, c) for c in courses]


@router.get("/courses/{course_id}", response_model=schemas.CourseOut)
def get_course(course_id: int,
               db: Session = Depends(get_db),
               user: models.User = Depends(auth_lib.get_current_user)):
    """课程详情。"""
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    return _course_out(db, course)


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
    """预约课程：名额校验，满员自动进候补名单。"""
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
    status = ST_BOOKED if _booked_count(db, course_id) < course.capacity else ST_WAITLIST
    booking = models.Booking(course_id=course_id, client_id=client.id, status=status)
    db.add(booking)
    db.commit()
    db.refresh(booking)
    audit_service.log(db, user.id, "booking.create", "booking", booking.id)
    return {"id": booking.id, "course_id": course_id, "client_id": client.id,
            "client_name": client.name, "status": booking.status}


@router.post("/courses/{course_id}/cancel")
def cancel_booking(course_id: int, body: dict | None = None,
                   db: Session = Depends(get_db),
                   user: models.User = Depends(auth_lib.get_current_user)):
    """取消预约：候补名单第一位自动转正。"""
    client = _resolve_client(db, user, (body or {}).get("client_id"))
    booking = (db.query(models.Booking)
               .filter(models.Booking.course_id == course_id,
                       models.Booking.client_id == client.id,
                       models.Booking.status.in_((ST_BOOKED, ST_WAITLIST))).first())
    if not booking:
        raise HTTPException(status_code=404, detail="没有可取消的预约")
    booking.status = ST_CANCELLED
    db.flush()  # session 为 autoflush=False，需手动刷入以便名额计数准确
    promoted = None
    if _booked_count(db, course_id) < db.query(models.Course).filter(
            models.Course.id == course_id).first().capacity:
        first = (db.query(models.Booking)
                 .filter(models.Booking.course_id == course_id,
                         models.Booking.status == ST_WAITLIST)
                 .order_by(models.Booking.created_at.asc()).first())
        if first:
            first.status = ST_BOOKED
            promoted = first.client_id
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
        method = "qr"
    else:
        if not data.client_id:
            raise HTTPException(status_code=400, detail="需指定客户")
        client = auth_lib.client_visible_to(db, user, data.client_id)
        method = "manual"
    booking = (db.query(models.Booking)
               .filter(models.Booking.course_id == course_id,
                       models.Booking.client_id == client.id,
                       models.Booking.status.in_((ST_BOOKED, ST_WAITLIST))).first())
    if not booking:
        raise HTTPException(status_code=400, detail="该客户未预约本课程")
    booking.status = ST_CHECKED_IN
    db.add(models.CheckIn(course_id=course_id, client_id=client.id, method=method))
    db.commit()
    update_attendance(db, client.id)
    audit_service.log(db, user.id, "booking.checkin", "booking", booking.id)
    return {"ok": True, "method": method}


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
    db.commit()
    for b in rows:
        update_attendance(db, b.client_id)
    audit_service.log(db, user.id, "booking.noshow", "course", course_id)
    return {"ok": True, "marked": len(rows)}


@router.get("/bookings/mine", response_model=list[schemas.BookingOut])
def my_bookings(db: Session = Depends(get_db),
                user: models.User = Depends(auth_lib.get_current_user)):
    """客户查看自己的约课记录。"""
    client = auth_lib.get_own_client(db, user)
    rows = (db.query(models.Booking)
            .filter(models.Booking.client_id == client.id)
            .order_by(models.Booking.created_at.desc()).all())
    return [{"id": b.id, "course_id": b.course_id, "client_id": b.client_id,
             "client_name": client.name, "status": b.status} for b in rows]
