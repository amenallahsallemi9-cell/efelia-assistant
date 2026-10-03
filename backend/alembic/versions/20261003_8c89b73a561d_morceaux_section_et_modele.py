"""Ajoute morceaux.section et morceaux.modele_embedding (vecteurs d'un même modèle).

Révision : 8c89b73a561d
Précédente : cd8d892256f8
Créée le : 2026-10-03 19:27:07.446774
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '8c89b73a561d'
down_revision: str | None = 'cd8d892256f8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("morceaux", sa.Column("section", sa.String(length=200), nullable=True))
    # Morceaux existants : modèle inconnu, ils seront réindexés.
    op.add_column(
        "morceaux",
        sa.Column(
            "modele_embedding", sa.String(length=120), nullable=False, server_default="inconnu"
        ),
    )
    op.alter_column("morceaux", "modele_embedding", server_default=None)
    op.create_index(
        op.f("ix_morceaux_modele_embedding"), "morceaux", ["modele_embedding"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_morceaux_modele_embedding"), table_name="morceaux")
    op.drop_column("morceaux", "modele_embedding")
    op.drop_column("morceaux", "section")
