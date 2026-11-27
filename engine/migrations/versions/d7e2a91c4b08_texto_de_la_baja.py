"""texto de la baja

Revision ID: d7e2a91c4b08
Revises: c4a1e0b97d22
Create Date: 2026-11-27 21:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7e2a91c4b08"
down_revision: str | None = "c4a1e0b97d22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("suppression") as batch:
        batch.add_column(sa.Column("detail", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("suppression") as batch:
        batch.drop_column("detail")
