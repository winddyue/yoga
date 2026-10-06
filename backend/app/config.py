# -*- coding: utf-8 -*-
"""全局配置：所有配置统一从环境变量读取，绝不在代码里写密钥。"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库连接串：默认 SQLite 零配置；
    # 如需切换 Postgres，设置 DATABASE_URL=postgresql://用户名:密码@主机:5432/库名
    DATABASE_URL: str = "sqlite:///./yoga.db"

    # JWT 签名密钥：生产环境必须通过环境变量覆盖默认值
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # token 有效期 7 天

    # 默认管理员账号：首次启动且用户表为空时自动创建
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # 第三方 API：密钥只能从环境变量读取，前端/日志绝不出现明文
    OCR_API_URL: str = ""   # 拍照识别接口地址（预留）
    OCR_API_KEY: str = ""   # 拍照识别密钥（环境变量）
    AI_API_URL: str = ""    # AI 接口地址（预留）
    AI_API_KEY: str = ""    # AI 接口密钥（环境变量）
    AI_MODEL: str = ""      # AI 模型名（非密钥，可在设置页修改）

    # 上传文件存放目录
    UPLOAD_DIR: str = "./uploads"

    class Config:
        env_file = ".env"  # 同时支持从 .env 文件读取
        extra = "ignore"


settings = Settings()
