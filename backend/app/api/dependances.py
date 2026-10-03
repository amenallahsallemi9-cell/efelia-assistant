"""Dépendances FastAPI partagées (remplaçables dans les tests)."""

import uuid
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Protocol

from fastapi import Depends, Request
from redis import Redis

from app.core.config import Parametres, get_parametres

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


def limite_debit(
    nom: str, limite: Callable[[Parametres], int], fenetre_s: int
) -> Callable[..., None]:
    """Dépendance FastAPI : au plus `limite` requêtes par adresse et par fenêtre."""

    def _verifier(
        requete: Request,
        client: Annotated[ClientRedis, Depends(get_redis)],
        parametres: Annotated[Parametres, Depends(get_parametres)],
    ) -> None:
        from app.api.erreurs import ErreurApi
        from app.core.securite import adresse_client, autoriser

        autorise, attente = autoriser(
            client, f"{nom}:{adresse_client(requete)}", limite(parametres), fenetre_s
        )
        if not autorise:
            raise ErreurApi(
                429,
                "TROP_DE_REQUETES",
                f"Trop de requêtes : réessayez dans {attente} secondes.",
                en_tetes={"Retry-After": str(attente)},
            )

    return _verifier


limiter_depots = limite_debit("depot", lambda p: p.limite_depots_par_heure, 3600)
limiter_eligibilite = limite_debit("eligibilite", lambda p: p.limite_eligibilite_par_minute, 60)
