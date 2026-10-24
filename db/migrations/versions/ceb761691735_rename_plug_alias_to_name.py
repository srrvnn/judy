"""rename plug alias to name

Revision ID: ceb761691735
Revises: 7c9ae3c92a7c
Create Date: 2026-10-24 13:11:10.381260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'ceb761691735'
down_revision: Union[str, Sequence[str], None] = '7c9ae3c92a7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("plugs") as batch_op:
        batch_op.alter_column("alias", new_column_name="name")


def downgrade() -> None:
    with op.batch_alter_table("plugs") as batch_op:
        batch_op.alter_column("name", new_column_name="alias")
