# -*- coding: utf-8 -*-
"""Alembic 环境：连接串与 app 共用 app/config.py 的 DATABASE_URL。

SQLite 下默认开启 batch 模式（render_as_batch），以支持
ALTER TABLE … ADD/DROP COLUMN 等受限操作。

常用命令（在 backend/ 目录下执行）：
  alembic upgrade head          升级到最新（改过 models.py 后执行）
  alembic downgrade -1          回滚一个版本
  alembic revision --autogenerate -m "描述"   models.py 改动后生成新迁移

注意：alembic.ini 必须保持纯 ASCII。Python 的 configparser 读 ini 时固定用
encoding="locale"（见 alembic/util/compat.py），在中文 Windows 上即 GBK，
ini 里一旦出现中文就会 UnicodeDecodeError，导致 upgrade 直接失败。
中文说明请写在本文件（有 -*- coding: utf-8 -*- 声明），不要写进 ini。
"""
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# backend/ 加入 sys.path，使 `import app.…` 可用
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
import app.models  # noqa: E402,F401  # 注册全部模型到 Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
