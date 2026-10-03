"""Schéma initial : dossiers, pages, pièces, morceaux (pgvector), décisions, traces.

Révision : 1c564b527151
Précédente : 
Créée le : 2026-10-03 11:23:06.498609
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '1c564b527151'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ENUMS = (
    "statut_pipeline",
    "verdict",
    "source_morceau",
    "type_piece",
    "methode_extraction",
    "confiance",
)


def upgrade() -> None:
    # pgvector doit être disponible avant de créer la colonne `embedding`.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('dossiers',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('nom', sa.String(length=120), nullable=False),
    sa.Column('prenom', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('formation', sa.String(length=255), nullable=False),
    sa.Column('heures_ia', sa.Integer(), nullable=False),
    sa.Column('alternance', sa.Boolean(), nullable=False),
    sa.Column('autre_bourse', sa.Boolean(), nullable=False),
    sa.Column('autre_bourse_libelle', sa.String(length=255), nullable=True),
    sa.Column('bourse_crous', sa.Boolean(), nullable=False),
    sa.Column('date_reception', sa.DateTime(timezone=True), nullable=False),
    sa.Column('nom_fichier', sa.String(length=255), nullable=False),
    sa.Column('chemin_fichier', sa.String(length=512), nullable=False),
    sa.Column('nb_pages', sa.Integer(), nullable=True),
    sa.Column('statut_pipeline', sa.Enum('RECU', 'EXTRAIT', 'CLASSE', 'LU', 'INDEXE', 'INSTRUIT', 'ERREUR', name='statut_pipeline'), nullable=False),
    sa.Column('message_erreur', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dossiers_created_at'), 'dossiers', ['created_at'], unique=False)
    op.create_index(op.f('ix_dossiers_statut_pipeline'), 'dossiers', ['statut_pipeline'], unique=False)
    op.create_table('decisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dossier_id', sa.UUID(), nullable=False),
    sa.Column('statut_regles', sa.Enum('RECEVABLE', 'A_COMPLETER', 'NON_RECEVABLE', name='verdict'), nullable=False),
    sa.Column('statut_propose_llm', sa.Enum('RECEVABLE', 'A_COMPLETER', 'NON_RECEVABLE', name='verdict'), nullable=True),
    sa.Column('garde_fou_declenche', sa.Boolean(), nullable=False),
    sa.Column('motifs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('avertissements', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('conseils', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('rapport', sa.Text(), nullable=False),
    sa.Column('modele', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['dossier_id'], ['dossiers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_decisions_dossier_id'), 'decisions', ['dossier_id'], unique=False)
    op.create_table('morceaux',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source', sa.Enum('dossier', 'reglement', name='source_morceau'), nullable=False),
    sa.Column('dossier_id', sa.UUID(), nullable=True),
    sa.Column('type_piece', sa.Enum('certificat_scolarite', 'cv', 'releve_notes', 'lettre_motivation', 'attestation_non_cumul', 'lettre_recommandation', 'justificatif_social', 'justificatif_handicap', 'autre', name='type_piece'), nullable=True),
    sa.Column('page', sa.Integer(), nullable=True),
    sa.Column('texte', sa.Text(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=False),
    sa.Column('tsv', postgresql.TSVECTOR(), sa.Computed("to_tsvector('french', texte)", persisted=True), nullable=False),
    sa.ForeignKeyConstraint(['dossier_id'], ['dossiers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_morceaux_dossier_id'), 'morceaux', ['dossier_id'], unique=False)
    op.create_index('ix_morceaux_embedding_hnsw', 'morceaux', ['embedding'], unique=False, postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.create_index(op.f('ix_morceaux_source'), 'morceaux', ['source'], unique=False)
    op.create_index('ix_morceaux_tsv', 'morceaux', ['tsv'], unique=False, postgresql_using='gin')
    op.create_table('pages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dossier_id', sa.UUID(), nullable=False),
    sa.Column('numero', sa.Integer(), nullable=False),
    sa.Column('texte', sa.Text(), nullable=True),
    sa.Column('methode', sa.Enum('texte', 'ocr', name='methode_extraction'), nullable=False),
    sa.Column('type_piece', sa.Enum('certificat_scolarite', 'cv', 'releve_notes', 'lettre_motivation', 'attestation_non_cumul', 'lettre_recommandation', 'justificatif_social', 'justificatif_handicap', 'autre', name='type_piece'), nullable=True),
    sa.Column('confiance_classification', sa.Float(), nullable=True),
    sa.Column('sensible', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['dossier_id'], ['dossiers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dossier_id', 'numero')
    )
    op.create_index(op.f('ix_pages_dossier_id'), 'pages', ['dossier_id'], unique=False)
    op.create_table('pieces',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dossier_id', sa.UUID(), nullable=False),
    sa.Column('type', sa.Enum('certificat_scolarite', 'cv', 'releve_notes', 'lettre_motivation', 'attestation_non_cumul', 'lettre_recommandation', 'justificatif_social', 'justificatif_handicap', 'autre', name='type_piece'), nullable=False),
    sa.Column('pages', sa.ARRAY(sa.Integer()), nullable=False),
    sa.Column('donnees_extraites', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('confiance', sa.Enum('haute', 'moyenne', 'faible', name='confiance'), nullable=False),
    sa.ForeignKeyConstraint(['dossier_id'], ['dossiers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pieces_dossier_id'), 'pieces', ['dossier_id'], unique=False)
    op.create_table('traces_agent',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dossier_id', sa.UUID(), nullable=False),
    sa.Column('ordre', sa.Integer(), nullable=False),
    sa.Column('outil', sa.String(length=80), nullable=False),
    sa.Column('arguments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('resultat', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('duree_ms', sa.Integer(), nullable=False),
    sa.Column('tokens', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['dossier_id'], ['dossiers.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_traces_agent_dossier_id'), 'traces_agent', ['dossier_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_traces_agent_dossier_id'), table_name='traces_agent')
    op.drop_table('traces_agent')
    op.drop_index(op.f('ix_pieces_dossier_id'), table_name='pieces')
    op.drop_table('pieces')
    op.drop_index(op.f('ix_pages_dossier_id'), table_name='pages')
    op.drop_table('pages')
    op.drop_index('ix_morceaux_tsv', table_name='morceaux', postgresql_using='gin')
    op.drop_index(op.f('ix_morceaux_source'), table_name='morceaux')
    op.drop_index('ix_morceaux_embedding_hnsw', table_name='morceaux', postgresql_using='hnsw', postgresql_ops={'embedding': 'vector_cosine_ops'})
    op.drop_index(op.f('ix_morceaux_dossier_id'), table_name='morceaux')
    op.drop_table('morceaux')
    op.drop_index(op.f('ix_decisions_dossier_id'), table_name='decisions')
    op.drop_table('decisions')
    op.drop_index(op.f('ix_dossiers_statut_pipeline'), table_name='dossiers')
    op.drop_index(op.f('ix_dossiers_created_at'), table_name='dossiers')
    op.drop_table('dossiers')
    for nom in ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {nom}")
