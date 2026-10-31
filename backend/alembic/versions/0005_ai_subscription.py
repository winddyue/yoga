# -*- coding: utf-8 -*-
"""AI 会员订阅制：products 加 kind/duration_days，新表 client_subscriptions，
399 团购卡下架，种子 3 档订阅套餐（初始默认价，馆主可改）。

Revision ID: 0005_ai_subscription
Revises: 0004_wxpay_orders
Create Date: 2026-10-31

幂等设计：新库由 create_all 建出完整表结构，本迁移检测到表/列已存在
自动跳过；老库执行补齐。种子：同名商品已存在则跳过。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_ai_subscription"
down_revision: Union[str, None] = "0004_wxpay_orders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUBSCRIPTION_SEEDS = [
    # (name, price_cents, duration_days, description) —— 占位价，馆主后定
    ("AI 会员月卡", 2900, 30, "AI 功能 30 天使用权：AI 生成训练计划、AI 生成饮食方案"),
    ("AI 会员季卡", 7900, 90, "AI 功能 90 天使用权：AI 生成训练计划、AI 生成饮食方案"),
    ("AI 会员年卡", 29900, 365, "AI 功能 365 天使用权：AI 生成训练计划、AI 生成饮食方案"),
]


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "products", "kind"):
        op.add_column("products", sa.Column("kind", sa.String(16),
                                            server_default="subscription",
                                            nullable=False))
    if not _has_column(bind, "products", "duration_days"):
        op.add_column("products", sa.Column("duration_days", sa.Integer(),
                                            server_default="0", nullable=False))

    if "client_subscriptions" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "client_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("client_id", sa.Integer(),
                      sa.ForeignKey("clients.id"), nullable=False, index=True),
            sa.Column("product_id", sa.Integer(),
                      sa.ForeignKey("products.id"), nullable=False),
            sa.Column("order_id", sa.Integer(),
                      sa.ForeignKey("orders.id"), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
            sa.Column("status", sa.String(16), nullable=False,
                      server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )

    # 399 团购卡下架（订阅制取代团购；已售订单不受影响）
    bind.execute(sa.text(
        "UPDATE products SET active = 0 WHERE name = '双十一399团购卡'"))

    # 种子 3 档订阅套餐（幂等：同名已存在则跳过）
    for name, price, days, desc in SUBSCRIPTION_SEEDS:
        existing = bind.execute(
            sa.text("SELECT COUNT(*) FROM products WHERE name = :n"),
            {"n": name},
        ).scalar()
        if not existing:
            bind.execute(
                sa.text(
                    "INSERT INTO products (name, price_cents, description, "
                    "kind, duration_days, active, created_at) "
                    "VALUES (:n, :p, :d, 'subscription', :dd, 1, "
                    "CURRENT_TIMESTAMP)"
                ),
                {"n": name, "p": price, "d": desc, "dd": days},
            )


def downgrade() -> None:
    op.drop_table("client_subscriptions")
    op.drop_column("products", "duration_days")
    op.drop_column("products", "kind")
