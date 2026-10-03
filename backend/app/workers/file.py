"""Mise en file des traitements de dossiers (RQ)."""

import uuid

from redis import Redis
from rq import Queue

from app.core.config import get_parametres

NOM_FILE = "dossiers"
DELAI_MAX_SECONDES = 15 * 60


def file_dossiers() -> Queue:
    """File RQ des dossiers."""
    return Queue(NOM_FILE, connection=Redis.from_url(get_parametres().redis_url))


def mettre_en_file(
    dossier_id: uuid.UUID, fonction: str = "app.workers.pipeline.traiter_dossier"
) -> str:
    """Planifie un traitement du dossier ; retourne l'identifiant de la tâche."""
    tache = file_dossiers().enqueue(
        fonction,
        str(dossier_id),
        job_timeout=DELAI_MAX_SECONDES,
        result_ttl=3600,
        failure_ttl=24 * 3600,
    )
    return str(tache.id)
