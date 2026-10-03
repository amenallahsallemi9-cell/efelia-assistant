"""Moteur et sessions SQLAlchemy."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_parametres


@lru_cache
def get_moteur() -> Engine:
    """Moteur partagé par le processus (pool de connexions)."""
    return create_engine(get_parametres().database_url, pool_pre_ping=True)


@lru_cache
def _fabrique() -> sessionmaker[Session]:
    return sessionmaker(bind=get_moteur(), expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dépendance FastAPI : ouvre une session et la ferme après la requête."""
    with _fabrique()() as session:
        yield session
