# -*- coding: utf-8 -*-
"""全局配置：所有配置统一从环境变量读取，绝不在代码里写密钥。"""
import sys

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 运行环境：dev（开发）/ prod（生产）。生产模式下安全检查更严格。
    # 用 ENV=prod 或 PROD=true 开启生产模式。
    ENV: str = "dev"
    PROD: bool = False

    # 数据库连接串：默认 SQLite 零配置；
    # 如需切换 Postgres，设置 DATABASE_URL=postgresql://用户名:密码@主机:5432/库名
    DATABASE_URL: str = "sqlite:///./yoga.db"

    # JWT 签名密钥：生产环境必须通过环境变量覆盖默认值
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # token 有效期 7 天

    # 默认管理员账号：首次启动且用户表为空时自动创建
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # CORS 白名单：逗号分隔。默认只允许本地开发源，生产必须配置为真实域名。
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    # 第三方 API：密钥只能从环境变量读取，前端/日志绝不出现明文
    OCR_API_URL: str = ""   # 拍照识别接口地址（预留）
    OCR_API_KEY: str = ""   # 拍照识别密钥（环境变量）
    AI_API_URL: str = ""    # AI 接口地址（预留，OpenAI 兼容）
    AI_API_KEY: str = ""    # AI 接口密钥（环境变量）
    AI_MODEL: str = ""      # AI 模型名（非密钥，可在设置页修改）
    ASR_API_URL: str = ""   # 语音识别接口地址（预留）
    ASR_API_KEY: str = ""   # 语音识别密钥（环境变量）

    # 敏感字段加密密钥（Fernet 格式）；未配置时为开发模式（文档标注风险）
    DATA_ENC_KEY: str = ""

    # 上传文件存放目录
    UPLOAD_DIR: str = "./uploads"
    # 单个上传文件大小上限（字节），默认 10MB
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024

    # 微信小程序登录：AppID/Secret 从公众平台获取，只走环境变量
    WX_APPID: str = ""
    WX_SECRET: str = ""
    # 开发模式模拟：true 时 wx.login 的 code 用 "mock:任意标识" 即可换取
    # mock openid，方便本地/CI 无真实微信环境时联调。生产模式禁止开启。
    WX_DEV_MOCK: bool = False

    # 签到时间窗（分钟）：客户扫码签到仅允许 [开课前 CHECKIN_OPEN_MIN,
    # 开课后 CHECKIN_CLOSE_MIN] 内进行；教练手动补签不受限制
    CHECKIN_OPEN_MIN: int = 30
    CHECKIN_CLOSE_MIN: int = 60

    class Config:
        env_file = ".env"  # 同时支持从 .env 文件读取
        extra = "ignore"


settings = Settings()


def is_prod() -> bool:
    """是否生产模式。"""
    return settings.PROD or settings.ENV.lower() == "prod"


def validate_prod():
    """生产模式安全基线检查：不通过直接抛错，阻止应用启动。

    开发模式下仅打印警告，不阻止启动。
    """
    problems = []
    if settings.SECRET_KEY == "change-me-in-production":
        problems.append("SECRET_KEY 仍是默认值，生产环境必须设置随机密钥")
    if settings.ADMIN_PASSWORD == "admin123":
        problems.append("ADMIN_PASSWORD 仍是默认值，生产环境必须修改")
    if not settings.DATA_ENC_KEY:
        problems.append("未设置 DATA_ENC_KEY，手机号等敏感字段将明文存储")
    if settings.WX_DEV_MOCK:
        problems.append("WX_DEV_MOCK 已开启（微信登录模拟），生产环境必须关闭")
    if not problems:
        return
    msg = "生产环境安全检查不通过：\n- " + "\n- ".join(problems)
    if is_prod():
        raise RuntimeError(msg)
    print("[警告] " + msg.replace("\n", "\n[警告] "), file=sys.stderr)
