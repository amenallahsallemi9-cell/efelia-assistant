"""Dépendances FastAPI partagées (remplaçables dans les tests)."""

import uuid
from functools import lru_cache
from typing import Protocol

from redis import Redis

from app.core.config import get_parametres

ClientRedis = Redis


@lru_cache
def get_redis() -> ClientRedis:
    """Client Redis partagé (connexion paresseuse)."""
    return Redis.from_url(get_parametres().redis_url, socket_connect_timeout=2)


class Planificateur(Protocol):
    """Planifie les traitements asynchrones (worker)."""

    def planifier_traitement(self, dossier_id: uuid.UUID) -> None:
        """Pipeline complet d'un nouveau dossier."""

    def planifier_instruction(self, dossier_id: uuid.UUID) -> None:
        """Nouvelle instruction (ou pipeline complet si le dossier n'est pas indexé)."""


class PlanificateurRQ:
    """Planification via la file RQ."""

    def planifier_traitement(self, dossier_id: uuid.UUID) -> None:
        """Met le pipeline complet en file."""
        from app.workers.file import mettre_en_file

        mettre_en_file(dossier_id)

    def planifier_instruction(self, dossier_id: uuid.UUID) -> None:
        """Met la relance de l'agent en file."""
        from app.workers.file import mettre_en_file

        mettre_en_file(dossier_id, fonction="app.workers.pipeline.relancer_instruction")


def get_planificateur() -> Planificateur:
    """Planificateur utilisé par l'API."""
    return PlanificateurRQ()
