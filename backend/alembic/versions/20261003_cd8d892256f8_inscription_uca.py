"""Ajoute dossiers.inscrit_uca (condition d'éligibilité déclarée).

Révision : cd8d892256f8
Précédente : 1c564b527151
Créée le : 2026-10-03 11:32:34.306408
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'cd8d892256f8'
down_revision: str | None = '1c564b527151'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Valeur par défaut temporaire pour les dossiers existants, puis retirée.
    op.add_column(
        "dossiers",
        sa.Column("inscrit_uca", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("dossiers", "inscrit_uca", server_default=None)


def downgrade() -> None:
    op.drop_column("dossiers", "inscrit_uca")
