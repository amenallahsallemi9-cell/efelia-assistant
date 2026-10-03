"""Ajoute decisions.controles : instantané de tous les contrôles (audit, checklist).

Révision : 51dc6c4f3a1f
Précédente : 8c89b73a561d
Créée le : 2026-10-03 19:33:01.710116
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
revision: str = '51dc6c4f3a1f'
down_revision: str | None = '8c89b73a561d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column(
            "controles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("decisions", "controles", server_default=None)


def downgrade() -> None:
    op.drop_column("decisions", "controles")
