"""Tâche de purge quotidienne (RQ) et commande `python -m app.workers.purge`."""

import logging
import uuid
from datetime import timedelta

from rq import Queue

from app.core.config import get_parametres
from app.core.logs import configurer_logs
from app.db.session import fabrique_sessions
from app.services.purge import BilanPurge, purger

logger = logging.getLogger(__name__)

PREFIXE_TACHE = "purge-quotidienne-"
INTERVALLE = timedelta(days=1)


def executer_purge() -> BilanPurge:
    """Purge selon `RETENTION_JOURS`."""
    parametres = get_parametres()
    with fabrique_sessions()() as session:
        return purger(session, parametres.stockage_dir, parametres.retention_jours)


def tache_purge() -> str:
    """Tâche RQ : purge, puis se replanifie dans 24 h."""
    from app.workers.file import file_dossiers

    bilan = executer_purge()
    planifier_purge(file_dossiers(), delai=INTERVALLE)
    return f"{bilan.dossiers_effaces} dossier(s), {bilan.fichiers_orphelins} orphelin(s)"


def planifier_purge(file: Queue, delai: timedelta = timedelta(0)) -> bool:
    """Planifie la prochaine purge si aucune n'est déjà prévue ; True si une tâche est créée.

    Chaque exécution a son propre identifiant : la purge en cours (statut « started »)
    peut ainsi planifier la suivante sans être confondue avec elle.
    """
    deja_prevue = [
        i
        for i in (*file.scheduled_job_registry.get_job_ids(), *file.get_job_ids())
        if i.startswith(PREFIXE_TACHE)
    ]
    if deja_prevue:
        return False
    file.enqueue_in(
        delai,
        tache_purge,
        job_id=f"{PREFIXE_TACHE}{uuid.uuid4().hex[:12]}",
        result_ttl=7 * 24 * 3600,
    )
    return True


if __name__ == "__main__":
    configurer_logs(get_parametres().log_level)
    resultat = executer_purge()
    print(
        f"Purge : {resultat.dossiers_effaces} dossier(s) expiré(s), "
        f"{resultat.fichiers_orphelins} fichier(s) orphelin(s) supprimé(s)."
    )
