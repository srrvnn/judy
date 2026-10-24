"""add message resolved fields

Revision ID: 54424f09207c
Revises: 0383785a56e0
Create Date: 2026-10-24 14:32:01.330184

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '54424f09207c'
down_revision: Union[str, Sequence[str], None] = '0383785a56e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(sa.Column("resolved_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("resolved_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_column("resolved_by")
        batch_op.drop_column("resolved_at")
