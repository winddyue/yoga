# -*- coding: utf-8 -*-
"""OCR 识别接口预留：拍照识别纸质体测单的第三方对接位。

当前为占位实现——只有当环境变量 OCR_API_URL / OCR_API_KEY 都配置后，
才会在此处按供应商文档实现具体调用。现在直接返回明确的未配置提示，
避免静默失败。密钥只从环境变量读取，绝不打印到日志。
"""
from ..config import settings


class OcrNotConfigured(Exception):
    """OCR 服务未配置时抛出。"""


def extract_assessment_from_image(image_bytes: bytes) -> dict:
    """从体测单照片中提取评估字段。

    未来对接时：在此处用 OCR_API_URL / OCR_API_KEY 调用第三方接口，
    把识别结果映射为 {"weight_kg": ..., "body_fat_pct": ..., ...} 返回。
    """
    if not settings.OCR_API_URL or not settings.OCR_API_KEY:
        raise OcrNotConfigured("未配置 OCR 服务：请在设置页填写接口地址，并在服务器环境变量中配置 OCR_API_KEY")
    # 预留：此处按具体 OCR 供应商的接口文档实现调用
    raise NotImplementedError("OCR 具体供应商对接尚未实现")
