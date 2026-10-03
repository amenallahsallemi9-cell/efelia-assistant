"""Conservation limitée (RGPD) : purge des dossiers expirés et des fichiers orphelins."""

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.modeles import Dossier
from app.services.effacement import effacer_dossier

logger = logging.getLogger(__name__)

#: Un fichier sans dossier n'est supprimé qu'après ce délai (dépôt peut-être en cours).
DELAI_ORPHELIN = timedelta(hours=1)


@dataclass(frozen=True)
class BilanPurge:
    """Résultat d'une purge."""

    dossiers_effaces: int
    fichiers_orphelins: int


def purger_dossiers_expires(
    session: Session, stockage: Path, retention_jours: int, maintenant: datetime | None = None
) -> int:
    """Efface les dossiers déposés il y a plus de `retention_jours` jours."""
    limite = (maintenant or datetime.now(UTC)) - timedelta(days=retention_jours)
    expires = session.scalars(select(Dossier).where(Dossier.created_at < limite)).all()
    for dossier in expires:
        effacer_dossier(session, dossier, stockage)
    return len(expires)


def nettoyer_fichiers_orphelins(
    session: Session, stockage: Path, maintenant: float | None = None
) -> int:
    """Supprime les PDF du stockage qui ne correspondent à aucun dossier (anciens d'1 h)."""
    if not stockage.exists():
        return 0
    connus = {Path(c).name for c in session.scalars(select(Dossier.chemin_fichier))}
    seuil = (maintenant or time.time()) - DELAI_ORPHELIN.total_seconds()
    supprimes = 0
    for fichier in stockage.iterdir():
        if not fichier.is_file() or fichier.suffix not in {".pdf", ".part"}:
            continue
        if fichier.name not in connus and fichier.stat().st_mtime < seuil:
            fichier.unlink(missing_ok=True)
            supprimes += 1
    return supprimes


def purger(
    session: Session, stockage: Path, retention_jours: int, maintenant: datetime | None = None
) -> BilanPurge:
    """Purge complète : dossiers expirés puis fichiers orphelins."""
    bilan = BilanPurge(
        dossiers_effaces=purger_dossiers_expires(session, stockage, retention_jours, maintenant),
        fichiers_orphelins=nettoyer_fichiers_orphelins(
            session, stockage, maintenant.timestamp() if maintenant else None
        ),
    )
    logger.info(
        "Purge terminée",
        extra={
            "etape": "PURGE",
            "statut": f"{bilan.dossiers_effaces} dossier(s), "
            f"{bilan.fichiers_orphelins} orphelin(s)",
        },
    )
    return bilan
