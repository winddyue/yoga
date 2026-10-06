# -*- coding: utf-8 -*-
"""智能录入：拍照 / 语音 / 聊天框自由文本，统一走"抽字段 → 人工确认 → 入库"流程。

- 拍照：复用 OCR 预留接口（见 services/ocr.py 及 docs/ocr-integration.md）
- 语音：上传音频，转文字（ASR 供应商可配置，未配置返回 501）
- 聊天框：自由文本调大模型抽取结构化字段，返回待确认结果，确认后才入库
"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import auth as auth_lib
from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..services import ai_gate, audit as audit_service
from ..services import llm as llm_service

router = APIRouter(prefix="/api/intake", tags=["智能录入"])

# 允许上传的音频类型
ALLOWED_AUDIO = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/x-m4a",
                 "audio/webm", "audio/ogg"}


class AsrNotConfigured(Exception):
    """语音识别未配置时抛出。"""


def _asr_transcribe(audio_bytes: bytes, content_type: str) -> str:
    """语音转文字：ASR 供应商对接位（可配置）。

    在设置页填写 asr_api_url，并在服务器环境变量配置 ASR_API_KEY 后，
    按具体供应商文档在此实现调用。现在返回明确提示，避免静默失败。
    """
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        row = db.query(models.Setting).filter(models.Setting.key == "asr_api_url").first()
        url = (row.value if row else "") or settings.ASR_API_URL
    finally:
        db.close()
    if not url or not settings.ASR_API_KEY:
        raise AsrNotConfigured("未配置语音识别：请在设置页填写接口地址，并在服务器环境变量中配置 ASR_API_KEY")
    # 预留：按具体 ASR 供应商（如阿里云/腾讯云/讯飞）的接口文档实现调用
    raise NotImplementedError("语音识别具体供应商对接尚未实现，详见 docs/ocr-integration.md")


@router.post("/voice")
def voice_to_text(file: UploadFile = File(...),
                   db: Session = Depends(get_db),
                   user: models.User = Depends(auth_lib.get_current_user)):
    """语音录入：上传音频 -> 转文字（AI 准入校验 + 用量统计）。"""
    ai_gate.check_ai_access(db, user)
    if file.content_type not in ALLOWED_AUDIO:
        raise HTTPException(status_code=400, detail="仅支持 MP3/WAV/M4A/WebM/OGG 音频")
    try:
        text = _asr_transcribe(file.file.read(), file.content_type)
    except AsrNotConfigured as e:
        raise HTTPException(status_code=501, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    ai_gate.record_usage(db, user.id, "voice")
    return {"text": text}


@router.post("/extract", response_model=schemas.ExtractOut)
def extract_from_text(data: schemas.ExtractIn,
                      db: Session = Depends(get_db),
                      user: models.User = Depends(auth_lib.get_current_user)):
    """聊天框录入：自由文本 -> 大模型抽取结构化字段（待确认，不入库）。"""
    ai_gate.check_ai_access(db, user)
    if not data.text.strip():
        raise HTTPException(status_code=400, detail="输入文本不能为空")
    try:
        fields = llm_service.extract_fields(data.text)
    except llm_service.LlmNotConfigured as e:
        raise HTTPException(status_code=501, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    ai_gate.record_usage(db, user.id, "extract")
    return {"fields": fields, "raw_text": data.text}


@router.post("/confirm", response_model=schemas.AssessmentOut)
def confirm_intake(data: schemas.IntakeConfirmIn,
                   db: Session = Depends(get_db),
                   user: models.User = Depends(auth_lib.get_current_user)):
    """确认入库：人工确认抽取字段后写入评估记录（走同意校验）。"""
    client = auth_lib.client_visible_to(db, user, data.client_id)
    auth_lib.require_sensitive_consent(db, client)
    allowed = set(schemas.AssessmentIn.model_fields.keys())
    clean = {k: v for k, v in data.fields.items() if k in allowed}
    a = models.Assessment(client_id=client.id, **clean)
    db.add(a)
    db.commit()
    db.refresh(a)
    audit_service.log(db, user.id, "assessment.create", "assessment", a.id)
    return a
