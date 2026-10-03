"""Orchestration du pipeline d'un dossier : RECU → EXTRAIT → CLASSE → LU → INDEXE → INSTRUIT.

Chaque étape met à jour `statut_pipeline` et publie un événement (consommé par le flux
SSE de l'API). En cas d'échec, le dossier passe en ERREUR avec un message sûr (jamais
de contenu de document).
"""

import json
import logging
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.core.reglement import get_reglement
from app.db.modeles import Dossier
from app.domain.modeles import StatutPipeline
from app.domain.regles import Reglement
from app.providers import Fournisseurs, construire_fournisseurs
from app.services.agent.boucle import instruire_avec_agent
from app.services.classification import executer_classification
from app.services.extraction import (
    ErreurExtraction,
    FonctionOcr,
    executer_extraction,
    ocr_tesseract,
)
from app.services.indexation import indexer_dossier, indexer_reglement_fichier
from app.services.lecture import executer_lecture

logger = logging.getLogger(__name__)


class Publieur(Protocol):
    """Diffuse les événements de progression d'un dossier."""

    def publier(self, dossier_id: uuid.UUID, evenement: dict[str, Any]) -> None:
        """Publie un événement."""


class PublieurNul:
    """Publieur sans effet (scripts, tests)."""

    def publier(self, dossier_id: uuid.UUID, evenement: dict[str, Any]) -> None:
        """N'envoie rien."""


def canal_evenements(dossier_id: uuid.UUID) -> str:
    """Nom du canal Redis pub/sub d'un dossier."""
    return f"dossier:{dossier_id}:evenements"


class PublieurRedis:
    """Publie les événements sur Redis (pub/sub)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def publier(self, dossier_id: uuid.UUID, evenement: dict[str, Any]) -> None:
        """Publie l'événement en JSON sur le canal du dossier."""
        self._client.publish(canal_evenements(dossier_id), json.dumps(evenement, default=str))


class ErreurEtape(Exception):
    """Échec attendu d'une étape, avec un message affichable."""


@dataclass
class Contexte:
    """Dépendances mises à disposition des étapes."""

    session: Session
    dossier: Dossier
    parametres: Parametres
    fournisseurs: Fournisseurs
    reglement: Reglement
    ocr: FonctionOcr = ocr_tesseract
    donnees: dict[str, Any] = field(default_factory=dict)


Etape = Callable[[Contexte], None]


def etape_extraction(contexte: Contexte) -> None:
    """Extraction du texte et OCR."""
    try:
        executer_extraction(contexte.session, contexte.dossier, contexte.ocr)
    except ErreurExtraction as exc:
        raise ErreurEtape(str(exc)) from exc


def etape_classification(contexte: Contexte) -> None:
    """Type de chaque page et regroupement en pièces."""
    executer_classification(contexte.session, contexte.dossier, contexte.fournisseurs.llm)


def etape_lecture(contexte: Contexte) -> None:
    """Extraction structurée par pièce."""
    executer_lecture(contexte.session, contexte.dossier, contexte.fournisseurs.llm)


def etape_indexation(contexte: Contexte) -> None:
    """Embeddings du dossier (et du règlement s'il a changé)."""
    embeddings = contexte.fournisseurs.embeddings
    indexer_reglement_fichier(contexte.session, embeddings, contexte.parametres.reglement_texte)
    indexer_dossier(contexte.session, contexte.dossier, embeddings)


def etape_instruction(contexte: Contexte) -> None:
    """Instruction par l'agent ; le statut final est celui des règles."""
    instruire_avec_agent(
        contexte.session, contexte.dossier, contexte.reglement, contexte.fournisseurs
    )


#: Étapes du pipeline, complétées au fil des phases (classification, lecture…).
ETAPES: list[tuple[StatutPipeline, str, Etape]] = [
    (StatutPipeline.EXTRAIT, "extraction", etape_extraction),
    (StatutPipeline.CLASSE, "classification", etape_classification),
    (StatutPipeline.LU, "lecture", etape_lecture),
    (StatutPipeline.INDEXE, "indexation", etape_indexation),
    (StatutPipeline.INSTRUIT, "instruction", etape_instruction),
]


def _evenement(dossier: Dossier, **extra: Any) -> dict[str, Any]:
    return {
        "dossier_id": str(dossier.id),
        "statut": dossier.statut_pipeline.value,
        "horodatage": datetime.now(UTC).isoformat(),
        **extra,
    }


def executer_pipeline(
    session: Session,
    dossier_id: uuid.UUID,
    parametres: Parametres,
    publieur: Publieur,
    etapes: Sequence[tuple[StatutPipeline, str, Etape]] = ETAPES,
    ocr: FonctionOcr = ocr_tesseract,
    fournisseurs: Fournisseurs | None = None,
    reglement: Reglement | None = None,
) -> StatutPipeline:
    """Exécute les étapes dans l'ordre ; s'arrête à la première erreur."""
    dossier = session.get(Dossier, dossier_id)
    if dossier is None:
        raise LookupError(f"Dossier {dossier_id} introuvable.")
    contexte = Contexte(
        session=session,
        dossier=dossier,
        parametres=parametres,
        fournisseurs=fournisseurs or construire_fournisseurs(parametres),
        reglement=reglement or get_reglement(),
        ocr=ocr,
    )
    dossier.message_erreur = None

    for statut, nom, etape in etapes:
        debut = time.perf_counter()
        try:
            etape(contexte)
        except Exception as exc:
            session.rollback()
            dossier = session.get(Dossier, dossier_id)
            if dossier is None:  # supprimé pendant le traitement
                raise LookupError(f"Dossier {dossier_id} introuvable.") from exc
            message = (
                str(exc)
                if isinstance(exc, ErreurEtape)
                else f"Erreur inattendue pendant l'étape « {nom} »."
            )
            dossier.statut_pipeline = StatutPipeline.ERREUR
            dossier.message_erreur = message
            session.commit()
            logger.error(
                "Échec du pipeline",
                exc_info=exc,
                extra={"dossier_id": str(dossier_id), "etape": nom, "statut": "ERREUR"},
            )
            publieur.publier(dossier_id, _evenement(dossier, etape=nom, message=message))
            return StatutPipeline.ERREUR

        dossier.statut_pipeline = statut
        session.commit()
        duree_ms = round((time.perf_counter() - debut) * 1000)
        logger.info(
            "Étape terminée",
            extra={"dossier_id": str(dossier_id), "etape": nom, "duree_ms": duree_ms},
        )
        publieur.publier(dossier_id, _evenement(dossier, etape=nom, duree_ms=duree_ms))

    return dossier.statut_pipeline


def _executer_tache(
    dossier_id: str, etapes: Sequence[tuple[StatutPipeline, str, Etape]] | None
) -> str:
    from redis import Redis

    from app.core.config import get_parametres
    from app.db.session import fabrique_sessions

    parametres = get_parametres()
    publieur = PublieurRedis(Redis.from_url(parametres.redis_url))
    with fabrique_sessions()() as session:
        try:
            statut = executer_pipeline(
                session, uuid.UUID(dossier_id), parametres, publieur, etapes=etapes or ETAPES
            )
        except LookupError:
            # Dossier supprimé entre la mise en file et l'exécution : rien à faire.
            logger.info("Dossier supprimé avant traitement", extra={"dossier_id": dossier_id})
            return "SUPPRIME"
        return statut.value


def traiter_dossier(dossier_id: str) -> str:
    """Tâche RQ : pipeline complet."""
    return _executer_tache(dossier_id, None)


def etapes_de_relance(statut: StatutPipeline) -> Sequence[tuple[StatutPipeline, str, Etape]]:
    """Seule l'instruction est rejouée si le dossier est déjà indexé ; sinon tout le pipeline."""
    if statut in (StatutPipeline.INDEXE, StatutPipeline.INSTRUIT):
        return ETAPES[-1:]
    return ETAPES


def relancer_instruction(dossier_id: str) -> str:
    """Tâche RQ : nouvelle instruction du dossier."""
    from app.db.session import fabrique_sessions

    with fabrique_sessions()() as session:
        dossier = session.get(Dossier, uuid.UUID(dossier_id))
        if dossier is None:
            return "SUPPRIME"
        etapes = etapes_de_relance(dossier.statut_pipeline)
    return _executer_tache(dossier_id, etapes)
