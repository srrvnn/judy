"""add message severity

Revision ID: 0383785a56e0
Revises: ceb761691735
Create Date: 2026-10-24 14:30:31.468230

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '0383785a56e0'
down_revision: Union[str, Sequence[str], None] = 'ceb761691735'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(sa.Column("severity", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="info"))


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_column("severity")
