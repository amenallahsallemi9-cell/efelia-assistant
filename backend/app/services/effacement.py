"""Droit à l'effacement : suppression complète d'un dossier.

Une seule suppression en base efface, par cascade, les pages, les pièces, les
morceaux (embeddings), les décisions et les traces. Le fichier PDF est ensuite
supprimé du volume de stockage.
"""

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.modeles import Dossier

logger = logging.getLogger(__name__)


def chemin_dans_stockage(chemin: Path, stockage: Path) -> bool:
    """Vrai si le chemin désigne bien un fichier du dossier de stockage (anti-traversée)."""
    try:
        chemin.resolve().relative_to(stockage.resolve())
    except ValueError:
        return False
    return True


def effacer_dossier(session: Session, dossier: Dossier, stockage: Path) -> bool:
    """Supprime le dossier et son fichier ; renvoie False si le fichier n'a pas pu être effacé."""
    dossier_id = str(dossier.id)
    chemin = Path(dossier.chemin_fichier)
    session.delete(dossier)
    session.commit()

    if not chemin_dans_stockage(chemin, stockage):
        logger.error("Chemin de fichier hors du stockage", extra={"dossier_id": dossier_id})
        return False
    try:
        chemin.unlink(missing_ok=True)
    except OSError:
        logger.exception("Fichier non supprimé", extra={"dossier_id": dossier_id})
        return False
    logger.info("Dossier effacé", extra={"dossier_id": dossier_id, "statut": "EFFACE"})
    return True
