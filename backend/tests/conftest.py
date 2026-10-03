"""Fixtures partagées.

Les tests d'intégration utilisent une base dédiée (`TEST_DATABASE_URL`), remise à zéro
par les migrations Alembic au début de la session de tests. Aucun appel réseau externe.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Parametres, get_parametres
from app.db.session import get_session

RACINE_BACKEND = Path(__file__).resolve().parents[1]


def _url_test() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or get_parametres().test_database_url
    if not url:
        pytest.fail("TEST_DATABASE_URL doit être définie pour les tests d'intégration.")
    return url


def config_alembic(url: str) -> Config:
    """Configuration Alembic pointant vers la base donnée."""
    config = Config(str(RACINE_BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(RACINE_BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configurer_logs"] = False
    return config


@pytest.fixture(scope="session")
def url_base_test() -> str:
    """URL de la base de test."""
    return _url_test()


@pytest.fixture(scope="session")
def moteur_test(url_base_test: str) -> Iterator[Engine]:
    """Base de test migrée depuis zéro (downgrade puis upgrade)."""
    config = config_alembic(url_base_test)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    moteur = create_engine(url_base_test)
    yield moteur
    moteur.dispose()


@pytest.fixture
def session_test(moteur_test: Engine) -> Iterator[Session]:
    """Session isolée : tout est annulé à la fin du test."""
    connexion = moteur_test.connect()
    transaction = connexion.begin()
    session = sessionmaker(bind=connexion, join_transaction_mode="create_savepoint")()
    yield session
    session.close()
    transaction.rollback()
    connexion.close()


@pytest.fixture
def parametres_test(tmp_path: Path) -> Parametres:
    """Paramètres de test : mode démo, stockage temporaire."""
    return Parametres(
        llm_provider="fake",
        cohere_api_key=None,
        stockage_dir=tmp_path / "dossiers",
        regles_fichier=RACINE_BACKEND.parent / "config" / "regles_2026.yaml",
        reglement_texte=RACINE_BACKEND.parent / "config" / "reglement_2026.md",
        # Les tests déposent beaucoup de dossiers : la limitation est testée à part.
        limite_depots_par_heure=100_000,
        limite_eligibilite_par_minute=100_000,
    )


@pytest.fixture
def client(session_test: Session, parametres_test: Parametres) -> Iterator[TestClient]:
    """Client HTTP branché sur la base de test."""
    from app.main import app

    app.dependency_overrides[get_session] = lambda: session_test
    app.dependency_overrides[get_parametres] = lambda: parametres_test
    with TestClient(app) as client_http:
        yield client_http
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def reglement():  # type: ignore[no-untyped-def]
    """Règlement 2026 réel (config/regles_2026.yaml)."""
    from app.core.reglement import charger_reglement

    return charger_reglement(RACINE_BACKEND.parent / "config" / "regles_2026.yaml")
