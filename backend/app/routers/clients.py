# -*- coding: utf-8 -*-
"""客户路由：客户档案的增删改查；馆主看全馆，教练只看自己的客户。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/clients", tags=["客户"])


def _visible_query(db: Session, user: models.User):
    """按角色过滤客户查询。"""
    q = db.query(models.Client)
    if user.role != "owner":
        q = q.filter(models.Client.coach_id == user.id)
    return q


@router.get("", response_model=list[schemas.ClientOut])
def list_clients(db: Session = Depends(get_db),
                 user: models.User = Depends(auth_lib.get_current_user)):
    """客户列表。"""
    return _visible_query(db, user).order_by(models.Client.id.desc()).all()


@router.post("", response_model=schemas.ClientOut)
def create_client(data: schemas.ClientIn,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.get_current_user)):
    """新增客户：教练只能挂到自己名下，馆主可指定教练。"""
    coach_id = data.coach_id if user.role == "owner" else user.id
    client = models.Client(**{**data.model_dump(exclude={"coach_id"}), "coach_id": coach_id})
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=schemas.ClientOut)
def get_client(client_id: int,
               db: Session = Depends(get_db),
               user: models.User = Depends(auth_lib.get_current_user)):
    """客户详情。"""
    return auth_lib.client_visible_to(db, user, client_id)


@router.put("/{client_id}", response_model=schemas.ClientOut)
def update_client(client_id: int, data: schemas.ClientIn,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.get_current_user)):
    """更新客户档案。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    for k, v in data.model_dump(exclude={"coach_id"}).items():
        setattr(client, k, v)
    if user.role == "owner" and data.coach_id is not None:
        client.coach_id = data.coach_id
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}")
def delete_client(client_id: int,
                  db: Session = Depends(get_db),
                  user: models.User = Depends(auth_lib.get_current_user)):
    """删除客户（连带评估记录一起删）。"""
    client = auth_lib.client_visible_to(db, user, client_id)
    db.delete(client)
    db.commit()
    return {"ok": True}
