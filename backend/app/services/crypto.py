# -*- coding: utf-8 -*-
"""敏感字段加密：手机号等在入库前加密，出库时解密（基础版）。

密钥从环境变量 DATA_ENC_KEY 读取（Fernet 格式，可用
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` 生成）。
未配置密钥时为开发模式：原文存储并在文档中明确标注风险，生产环境必须配置。
存储格式加 "enc:" 前缀以区分是否已加密。
"""
import os

PREFIX = "enc:"


def _fernet():
    """未配置密钥时返回 None（开发模式回退）。"""
    key = os.environ.get("DATA_ENC_KEY", "")
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode())


def encrypt_phone(plain: str) -> str:
    """加密手机号；无密钥时原文返回。"""
    if not plain:
        return ""
    f = _fernet()
    if f is None:
        return plain
    return PREFIX + f.encrypt(plain.encode()).decode()


def decrypt_phone(stored: str) -> str:
    """解密手机号；非加密格式原文返回。"""
    if not stored:
        return ""
    if not stored.startswith(PREFIX):
        return stored
    f = _fernet()
    if f is None:
        return stored  # 密钥丢失时不抛错，由运维介入
    return f.decrypt(stored[len(PREFIX):].encode()).decode()
