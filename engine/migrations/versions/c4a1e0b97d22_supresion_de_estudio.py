"""supresión de estudio (kind lead)

Revision ID: c4a1e0b97d22
Revises: 2fb1d83b32e1
Create Date: 2026-11-27 20:40:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c4a1e0b97d22"
down_revision: str | None = "2fb1d83b32e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_suppression_kind",
        "suppression",
        "kind IN ('email', 'domain', 'phone', 'instagram', 'linkedin', 'lead')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_suppression_kind", "suppression", type_="check")
