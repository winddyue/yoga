# -*- coding: utf-8 -*-
"""每日打卡：新建 daily_checkins 表

Revision ID: 0003_daily_checkin
Revises: 0002_diet_source_notify
Create Date: 2026-10-08

幂等设计：与 0002 同风格，新库由 create_all 建出完整表结构，
本迁移检测到表已存在自动跳过；老库执行补齐。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_daily_checkin"
down_revision: Union[str, None] = "0002_diet_source_notify"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "daily_checkins" not in tables:
        op.create_table(
            "daily_checkins",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"),
                      nullable=False, index=True),
            sa.Column("date", sa.String(16), nullable=False, server_default=""),
            sa.Column("kind", sa.String(16), nullable=False,
                      server_default="training"),
            sa.Column("note", sa.Text(), nullable=False, server_default=""),
            sa.Column("photo_path", sa.String(256), nullable=False,
                      server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.UniqueConstraint("client_id", "date", "kind",
                                name="uq_checkin_client_date_kind"),
        )


def downgrade() -> None:
    if "daily_checkins" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("daily_checkins")
