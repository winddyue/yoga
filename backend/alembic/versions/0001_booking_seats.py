# -*- coding: utf-8 -*-
"""预约并发安全：courses.booked_seats 原子计数器 + 防重复预约部分唯一索引

Revision ID: 0001_booking_seats
Revises:
Create Date: 2026-10-08

幂等设计：新库由 app 启动时的 create_all 直接建出完整表结构，
本迁移检测到列/索引已存在会自动跳过；老库（create_all 建表、
后续 models.py 加列）执行本迁移补齐列、回填计数、建索引。
空库（表尚不存在）直接跳过——建表由 create_all 负责。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_booking_seats"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVE_STATUSES = "('booked','waitlist','checked_in')"
_OCCUPIED_STATUSES = "('booked','checked_in')"


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "courses" in tables:
        columns = {c["name"] for c in insp.get_columns("courses")}
        if "booked_seats" not in columns:
            op.add_column(
                "courses",
                sa.Column("booked_seats", sa.Integer(), nullable=False,
                          server_default="0"),
            )
            # 回填：已占座位 = 该课程下 booked + checked_in 的预约数
            op.execute(sa.text(
                "UPDATE courses SET booked_seats = ("
                "SELECT COUNT(*) FROM bookings "
                "WHERE bookings.course_id = courses.id "
                f"AND bookings.status IN {_OCCUPIED_STATUSES})"
            ))

    if "bookings" in tables:
        indexes = {i["name"] for i in insp.get_indexes("bookings")}
        if "uq_booking_active" not in indexes:
            # 部分唯一索引：同一客户同一课程只允许一条有效预约。
            # SQLite 与 Postgres 语法相同。
            op.execute(sa.text(
                "CREATE UNIQUE INDEX uq_booking_active "
                "ON bookings (course_id, client_id) "
                f"WHERE status IN {_ACTIVE_STATUSES}"
            ))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "bookings" in tables:
        indexes = {i["name"] for i in insp.get_indexes("bookings")}
        if "uq_booking_active" in indexes:
            op.drop_index("uq_booking_active", table_name="bookings")

    if "courses" in tables:
        columns = {c["name"] for c in insp.get_columns("courses")}
        if "booked_seats" in columns:
            op.drop_column("courses", "booked_seats")
