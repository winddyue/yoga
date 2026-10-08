# -*- coding: utf-8 -*-
"""AI 饮食双轨制 + 站内通知：diet_plans 加 source 列、新建 notifications 表

Revision ID: 0002_diet_source_notify
Revises: 0001_booking_seats
Create Date: 2026-10-08

幂等设计：与 0001 同风格，新库由 create_all 建出完整表结构，
本迁移检测到列/表已存在自动跳过；老库执行补齐。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_diet_source_notify"
down_revision: Union[str, None] = "0001_booking_seats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    # 1. diet_plans.source（'coach' / 'ai'），老数据默认 coach
    if "diet_plans" in tables:
        columns = {c["name"] for c in insp.get_columns("diet_plans")}
        if "source" not in columns:
            op.add_column(
                "diet_plans",
                sa.Column("source", sa.String(8), nullable=False,
                          server_default="coach"),
            )

    # 2. notifications 表
    if "notifications" not in tables:
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"),
                      nullable=False, index=True),
            sa.Column("type", sa.String(32), nullable=False, server_default=""),
            sa.Column("title", sa.String(128), nullable=False, server_default=""),
            sa.Column("body", sa.String(512), nullable=False, server_default=""),
            sa.Column("ref_type", sa.String(32), nullable=False, server_default=""),
            sa.Column("ref_id", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_read", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "notifications" in tables:
        op.drop_table("notifications")
    if "diet_plans" in tables:
        columns = {c["name"] for c in sa.inspect(bind).get_columns("diet_plans")}
        if "source" in columns:
            with op.batch_alter_table("diet_plans") as batch_op:
                batch_op.drop_column("source")
