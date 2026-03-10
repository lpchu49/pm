"""create initial schema

Revision ID: 20260310_0001
Revises:
Create Date: 2026-03-10

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260310_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "users",
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("username", sa.String(), nullable=False, unique=True),
    sa.Column("password", sa.String(), nullable=False),
  )

  op.create_table(
    "sessions",
    sa.Column("token", sa.String(), primary_key=True),
    sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("created_at", sa.String(), nullable=False),
    sa.Column("expires_at", sa.String(), nullable=False),
  )

  op.create_table(
    "boards",
    sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
    sa.Column("payload", sa.Text(), nullable=False),
    sa.Column("updated_at", sa.String(), nullable=False),
  )


def downgrade() -> None:
  op.drop_table("boards")
  op.drop_table("sessions")
  op.drop_table("users")
