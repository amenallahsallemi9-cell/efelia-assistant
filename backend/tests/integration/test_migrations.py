"""Les migrations Alembic sont cohérentes avec les modèles SQLAlchemy."""

from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from app.db.modeles import Base


def test_aucune_derive_entre_modeles_et_migrations(moteur_test: Engine) -> None:
    with moteur_test.connect() as connexion:
        differences = compare_metadata(MigrationContext.configure(connexion), Base.metadata)
    assert differences == []


def test_pgvector_et_index_hnsw(moteur_test: Engine) -> None:
    with moteur_test.connect() as connexion:
        assert connexion.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        definition = connexion.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_morceaux_embedding_hnsw'")
        ).scalar_one()
    assert "hnsw" in definition
    assert "vector_cosine_ops" in definition


def test_tables_attendues(moteur_test: Engine) -> None:
    tables = set(inspect(moteur_test).get_table_names())
    assert {"dossiers", "pages", "pieces", "morceaux", "decisions", "traces_agent"} <= tables
