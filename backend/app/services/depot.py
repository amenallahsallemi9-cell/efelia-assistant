"""Étape 1 : réception, validation stricte et stockage du fichier déposé."""

import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

import pymupdf
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.db.modeles import Dossier
from app.domain.modeles import StatutPipeline
from app.domain.regles import Reglement, bourse_est_compatible
from app.schemas import FicheDeclaree, date_reception

logger = logging.getLogger(__name__)

SIGNATURE_PDF = b"%PDF-"


class ErreurDepot(Exception):
    """Fichier refusé au dépôt, avec un code stable et un message en français."""

    def __init__(self, code: str, message: str, statut_http: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.statut_http = statut_http


def valider_pdf(contenu: bytes, parametres: Parametres) -> int:
    """Vérifie taille, type réel (signature), lisibilité et nombre de pages.

    Retourne le nombre de pages. Lève `ErreurDepot` sinon.
    """
    if not contenu:
        raise ErreurDepot("FICHIER_VIDE", "Le fichier est vide.")
    max_octets = parametres.max_taille_mo * 1024 * 1024
    if len(contenu) > max_octets:
        raise ErreurDepot(
            "FICHIER_TROP_VOLUMINEUX",
            f"Le fichier dépasse la taille maximale de {parametres.max_taille_mo} Mo.",
            413,
        )
    # Type MIME réel : on ne fait confiance ni à l'extension ni à l'en-tête HTTP.
    if not contenu[:1024].lstrip().startswith(SIGNATURE_PDF):
        raise ErreurDepot("TYPE_NON_PDF", "Le fichier n'est pas un PDF.", 415)
    try:
        document = pymupdf.open(stream=contenu, filetype="pdf")
    except Exception as exc:
        raise ErreurDepot("PDF_ILLISIBLE", "Le PDF est corrompu ou illisible.") from exc
    with document:
        if document.needs_pass:
            raise ErreurDepot(
                "PDF_PROTEGE", "Le PDF est protégé par un mot de passe : retirez la protection."
            )
        nb_pages: int = document.page_count
    if nb_pages == 0:
        raise ErreurDepot("PDF_VIDE", "Le PDF ne contient aucune page.")
    if nb_pages > parametres.max_pages:
        raise ErreurDepot(
            "TROP_DE_PAGES",
            f"Le PDF contient {nb_pages} pages (maximum {parametres.max_pages}).",
        )
    return nb_pages


def nettoyer_nom_fichier(nom: str) -> str:
    """Nom d'origine réduit à son nom de base (sans chemin), conservé pour le contrôle de format."""
    base = PureWindowsPath(PurePosixPath(nom).name).name
    base = "".join(c for c in base if c.isprintable()).strip()
    return base[:255] or "sans_nom.pdf"


def stocker_fichier(contenu: bytes, dossier_stockage: Path) -> Path:
    """Écrit le fichier sous un nom aléatoire, de façon atomique, lisible du seul service."""
    dossier_stockage.mkdir(parents=True, exist_ok=True)
    chemin = dossier_stockage / f"{uuid.uuid4().hex}.pdf"
    temporaire = chemin.with_suffix(".part")
    descripteur = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descripteur, "wb") as fichier:
        fichier.write(contenu)
    temporaire.replace(chemin)
    return chemin


def creer_dossier(
    session: Session,
    fiche: FicheDeclaree,
    nom_fichier: str,
    contenu: bytes,
    parametres: Parametres,
    reglement: Reglement,
    maintenant: datetime | None = None,
) -> Dossier:
    """Valide le PDF, le stocke et crée le dossier au statut RECU."""
    nb_pages = valider_pdf(contenu, parametres)
    chemin = stocker_fichier(contenu, parametres.stockage_dir)
    try:
        dossier = Dossier(
            nom=fiche.nom,
            prenom=fiche.prenom,
            email=fiche.email,
            formation=fiche.formation,
            inscrit_uca=fiche.inscrit_uca,
            heures_ia=fiche.heures_ia,
            alternance=fiche.alternance,
            autre_bourse=fiche.autre_bourse,
            autre_bourse_libelle=fiche.autre_bourse_libelle or None,
            bourse_crous=fiche.autre_bourse
            and bourse_est_compatible(fiche.autre_bourse_libelle, reglement),
            date_reception=date_reception(fiche, maintenant or datetime.now(UTC)),
            nom_fichier=nettoyer_nom_fichier(nom_fichier),
            chemin_fichier=str(chemin),
            nb_pages=nb_pages,
            statut_pipeline=StatutPipeline.RECU,
        )
        session.add(dossier)
        session.commit()
    except Exception:
        session.rollback()
        chemin.unlink(missing_ok=True)
        raise
    logger.info("Dossier reçu", extra={"dossier_id": str(dossier.id), "statut": "RECU"})
    return dossier
