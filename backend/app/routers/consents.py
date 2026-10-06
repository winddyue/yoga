# -*- coding: utf-8 -*-
"""合规：单独同意记录、用户数据权利（查看/更正/删除/注销）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db
from ..services import audit as audit_service
from ..services import crypto as crypto_service

router = APIRouter(prefix="/api", tags=["合规"])


@router.post("/consents", response_model=schemas.ConsentOut)
def record_consent(data: schemas.ConsentIn,
                   db: Session = Depends(get_db),
                   user: models.User = Depends(auth_lib.get_current_user)):
    """记录一次单独同意：客户为自己操作，工作人员可代客户登记。"""
    if user.role == "client":
        client = auth_lib.get_own_client(db, user)
        if data.client_id != client.id:
            raise HTTPException(status_code=403, detail="只能为自己登记同意")
    else:
        client = auth_lib.client_visible_to(db, user, data.client_id)
    if data.consent_type not in ("sensitive_info", "ai_processing"):
        raise HTTPException(status_code=400, detail="同意类型无效")
    consent = models.Consent(client_id=client.id, user_id=user.id,
                             consent_type=data.consent_type, version=data.version)
    db.add(consent)
    db.commit()
    db.refresh(consent)
    audit_service.log(db, user.id, "consent.record", "consent", consent.id)
    return {"id": consent.id, "client_id": consent.client_id,
            "consent_type": consent.consent_type, "version": consent.version}


@router.get("/consents/mine", response_model=list[schemas.ConsentOut])
def my_consents(db: Session = Depends(get_db),
                user: models.User = Depends(auth_lib.get_current_user)):
    """客户查看自己的同意记录。"""
    client = auth_lib.get_own_client(db, user)
    rows = (db.query(models.Consent)
            .filter(models.Consent.client_id == client.id)
            .order_by(models.Consent.created_at.desc()).all())
    return [{"id": c.id, "client_id": c.client_id, "consent_type": c.consent_type,
             "version": c.version} for c in rows]


@router.get("/me/data")
def export_my_data(db: Session = Depends(get_db),
                   user: models.User = Depends(auth_lib.get_current_user)):
    """用户权利：查看/导出个人数据（客户角色）。"""
    client = auth_lib.get_own_client(db, user)
    assessments = (db.query(models.Assessment)
                   .filter(models.Assessment.client_id == client.id)
                   .order_by(models.Assessment.date.asc()).all())
    plans = (db.query(models.TrainingPlan)
             .filter(models.TrainingPlan.client_id == client.id).all())
    diets = (db.query(models.DietPlan)
             .filter(models.DietPlan.client_id == client.id).all())
    bookings = (db.query(models.Booking)
                .filter(models.Booking.client_id == client.id).all())
    return {
        "profile": {"id": client.id, "name": client.name, "gender": client.gender,
                    "age": client.age, "height_cm": client.height_cm,
                    "phone": crypto_service.decrypt_phone(client.phone or ""),
                    "goal": client.goal},
        "assessments": [{"date": a.date, "weight_kg": a.weight_kg,
                         "body_fat_pct": a.body_fat_pct} for a in assessments],
        "plans": len(plans), "diets": len(diets),
        "bookings": [{"course_id": b.course_id, "status": b.status} for b in bookings],
    }


@router.put("/me/data")
def correct_my_data(data: schemas.ClientSelfUpdate,
                    db: Session = Depends(get_db),
                    user: models.User = Depends(auth_lib.get_current_user)):
    """用户权利：更正个人基础信息。"""
    client = auth_lib.get_own_client(db, user)
    payload = data.model_dump(exclude_none=True)
    if "phone" in payload:
        payload["phone"] = crypto_service.encrypt_phone(payload["phone"] or "")
    for k, v in payload.items():
        setattr(client, k, v)
    db.commit()
    audit_service.log(db, user.id, "client.self_update", "client", client.id)
    return {"ok": True}


@router.post("/me/deactivate")
def deactivate_me(db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.get_current_user)):
    """用户权利：注销账号（停用登录，数据保留备查）。"""
    user.is_active = False
    db.commit()
    audit_service.log(db, user.id, "user.deactivate", "user", user.id)
    return {"ok": True}


@router.delete("/me/data")
def delete_my_data(db: Session = Depends(get_db),
                   user: models.User = Depends(auth_lib.get_current_user)):
    """用户权利：删除个人数据（删除客户档案及关联记录，账号同步停用）。"""
    client = auth_lib.get_own_client(db, user)
    cid = client.id
    db.delete(client)
    user.is_active = False
    db.commit()
    audit_service.log(db, user.id, "client.self_delete", "client", cid)
    return {"ok": True}
