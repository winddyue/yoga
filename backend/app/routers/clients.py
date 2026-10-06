# -*- coding: utf-8 -*-
"""客户路由：客户档案的增删改查；馆主看全馆，教练只看自己的客户，
客户只看自己的档案且看不到教练内部备注（字段级权限）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db
from ..services import audit as audit_service
from ..services import crypto as crypto_service

router = APIRouter(prefix="/api/clients", tags=["客户"])


def _visible_query(db: Session, user: models.User):
    """按角色过滤客户查询。"""
    q = db.query(models.Client)
    if user.role == "owner":
        return q
    if user.role == "coach":
        return q.filter(models.Client.coach_id == user.id)
    # 客户角色只看自己
    return q.filter(models.Client.id == user.client_id)


def _present(client: models.Client, user: models.User) -> dict:
    """组装返回数据：手机号解密；客户角色看不到内部备注。"""
    data = {
        "id": client.id, "name": client.name, "gender": client.gender,
        "age": client.age, "height_cm": client.height_cm,
        "phone": crypto_service.decrypt_phone(client.phone or ""),
        "goal": client.goal, "coach_id": client.coach_id,
        "custom_values": client.custom_values or {},
        "attendance_rate": client.attendance_rate or 0,
        "is_minor": bool(client.is_minor),
        "guardian_consent": bool(client.guardian_consent),
    }
    # 字段级权限：只有工作人员能看到教练内部备注
    data["notes"] = client.notes or "" if user.role != "client" else ""
    return data


@router.get("", response_model=list[schemas.ClientOut])
def list_clients(db: Session = Depends(get_db),
                 user: models.User = Depends(auth_lib.get_current_user)):
    """客户列表。"""
    rows = _visible_query(db, user).order_by(models.Client.id.desc()).all()
    return [_present(c, user) for c in rows]


@router.get("/mine", response_model=schemas.ClientSelfOut)
def my_client(db: Session = Depends(get_db),
              user: models.User = Depends(auth_lib.get_current_user)):
    """客户查看自己的档案。"""
    return _present(auth_lib.get_own_client(db, user), user)


@router.post("", response_model=schemas.ClientOut)
def create_client(data: schemas.ClientIn,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.require_staff)):
    """新增客户：教练只能挂到自己名下，馆主可指定教练。手机号加密存储。"""
    if user.role == "client":
        # 客户角色走注册流程，不在此创建
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅工作人员可操作")
    coach_id = data.coach_id if user.role == "owner" else user.id
    payload = data.model_dump(exclude={"coach_id"})
    payload["phone"] = crypto_service.encrypt_phone(payload.get("phone") or "")
    client = models.Client(**payload, coach_id=coach_id)
    db.add(client)
    db.commit()
    db.refresh(client)
    audit_service.log(db, user.id, "client.create", "client", client.id)
    return _present(client, user)


# 我自己的客户档案（客户角色）。注意：必须定义在 /{client_id} 之前，
# 否则 "mine" 会被当成 client_id 匹配。
@router.get("/mine", response_model=schemas.ClientOut)
def my_client(
    db: Session = Depends(get_db),
    user: models.User = Depends(auth_lib.get_current_user),
):
    if user.role != "client" or not user.client_id:
        raise HTTPException(403, "仅客户角色可访问")
    client = db.get(models.Client, user.client_id)
    if not client:
        raise HTTPException(404, "未绑定客户档案")
    return _present(client, user)


@router.get("/{client_id}", response_model=schemas.ClientOut)
def get_client(client_id: int,
               db: Session = Depends(get_db),
               user: models.User = Depends(auth_lib.get_current_user)):
    """客户详情。"""
    return _present(auth_lib.client_visible_to(db, user, client_id), user)


@router.put("/{client_id}", response_model=schemas.ClientOut)
def update_client(client_id: int, data: schemas.ClientIn,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.require_staff)):
    """更新客户档案（工作人员）。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    payload = data.model_dump(exclude={"coach_id"})
    if payload.get("phone") is not None:
        payload["phone"] = crypto_service.encrypt_phone(payload["phone"] or "")
    for k, v in payload.items():
        setattr(client, k, v)
    if user.role == "owner" and data.coach_id is not None:
        client.coach_id = data.coach_id
    db.commit()
    db.refresh(client)
    audit_service.log(db, user.id, "client.update", "client", client.id)
    return _present(client, user)


@router.delete("/{client_id}")
def delete_client(client_id: int,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.require_staff)):
    """删除客户（连带评估记录一起删）。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    db.delete(client)
    db.commit()
    audit_service.log(db, user.id, "client.delete", "client", client_id)
    return {"ok": True}
