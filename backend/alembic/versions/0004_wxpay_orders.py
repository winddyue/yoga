# -*- coding: utf-8 -*-
"""微信支付：products / orders 表 + 种子商品 399 团购卡

Revision ID: 0004_wxpay_orders
Revises: 0003_daily_checkin
Create Date: 2026-10-31

幂等设计：与 0003 同风格，新库由 create_all 建出完整表结构，
本迁移检测到表已存在自动跳过；老库执行补齐。
种子商品：已存在同名商品则跳过。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_wxpay_orders"
down_revision: Union[str, None] = "0003_daily_checkin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "products" not in tables:
        op.create_table(
            "products",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(64), nullable=False),
            sa.Column("price_cents", sa.Integer(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )

    if "orders" not in tables:
        op.create_table(
            "orders",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("out_trade_no", sa.String(64), nullable=False),
            sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id"),
                      nullable=False, index=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"),
                      nullable=False, index=True),
            sa.Column("amount_cents", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False,
                      server_default="pending"),
            sa.Column("prepay_id", sa.String(128), nullable=False,
                      server_default=""),
            sa.Column("transaction_id", sa.String(64), nullable=False,
                      server_default=""),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.func.now()),
        )
        op.create_index("ix_orders_out_trade_no", "orders", ["out_trade_no"],
                        unique=True)

    # 种子商品：399 双十一团购卡（幂等：同名 active 商品已存在则跳过）
    existing = bind.execute(
        sa.text("SELECT COUNT(*) FROM products WHERE name = :n AND active = 1"),
        {"n": "双十一399团购卡"},
    ).scalar()
    if not existing:
        bind.execute(
            sa.text(
                "INSERT INTO products (name, price_cents, description, active) "
                "VALUES (:n, :p, :d, 1)"
            ),
            {
                "n": "双十一399团购卡",
                "p": 39900,
                "d": "身体评估私教×1 + 器械私教×1 + 普拉提小班两周 + 瑜伽团课14天；5人成团、团长免单",
            },
        )


def downgrade() -> None:
    op.drop_index("ix_orders_out_trade_no", table_name="orders")
    op.drop_table("orders")
    op.drop_table("products")
