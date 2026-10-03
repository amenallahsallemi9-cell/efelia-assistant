"""Étape 5 : découpage en morceaux et calcul des embeddings (pgvector).

Deux corpus : le règlement (indexé une fois par modèle d'embeddings) et chaque dossier.
Les pages sensibles (texte nul) ne sont jamais indexées. Chaque morceau garde le nom
du modèle qui l'a vectorisé : on ne compare jamais des vecteurs de modèles différents.
"""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.modeles import DIMENSION_EMBEDDING, Dossier, Morceau
from app.domain.modeles import SourceMorceau, TypePiece
from app.providers.base import EmbeddingProvider

logger = logging.getLogger(__name__)

TAILLE_MAX = 900
TAILLE_MIN = 25
_PHRASES = re.compile(r"(?<=[.!?;:])\s+|\n")
LIBELLES_PIECES = {
    TypePiece.CERTIFICAT_SCOLARITE: "Certificat de scolarité",
    TypePiece.CV: "Curriculum vitae",
    TypePiece.RELEVE_NOTES: "Relevé de notes",
    TypePiece.LETTRE_MOTIVATION: "Lettre de motivation",
    TypePiece.ATTESTATION_NON_CUMUL: "Attestation de non-cumul",
    TypePiece.LETTRE_RECOMMANDATION: "Lettre de recommandation",
    TypePiece.AUTRE: "Autre document",
}


@dataclass(frozen=True)
class MorceauPrepare:
    """Morceau avant vectorisation."""

    texte: str
    section: str | None = None
    page: int | None = None
    type_piece: TypePiece | None = None

    @property
    def texte_a_vectoriser(self) -> str:
        """Le titre de section aide la recherche sémantique (non stocké dans `texte`)."""
        return f"{self.section} — {self.texte}" if self.section else self.texte


def decouper(texte: str, taille_max: int = TAILLE_MAX) -> list[str]:
    """Découpe par paragraphes puis par phrases, avec une phrase de chevauchement."""
    morceaux: list[str] = []
    for paragraphe in re.split(r"\n\s*\n", texte):
        paragraphe = paragraphe.strip()
        if not paragraphe:
            continue
        if len(paragraphe) <= taille_max:
            morceaux.append(" ".join(paragraphe.split()))
            continue
        courant: list[str] = []
        for phrase in (p.strip() for p in _PHRASES.split(paragraphe)):
            if not phrase:
                continue
            if courant and len(" ".join([*courant, phrase])) > taille_max:
                morceaux.append(" ".join(courant))
                courant = courant[-1:] if len(courant[-1]) < taille_max // 2 else []
            courant.append(phrase[:taille_max])
        if courant:
            morceaux.append(" ".join(courant))
    utiles = [m for m in morceaux if len(m) >= TAILLE_MIN]
    return utiles or [m for m in morceaux if m][:1]


def preparer_reglement(texte: str) -> list[MorceauPrepare]:
    """Morceaux du règlement, rattachés à leur section (titres `## …`)."""
    morceaux: list[MorceauPrepare] = []
    for bloc in re.split(r"^## ", texte, flags=re.MULTILINE)[1:]:
        titre, _, corps = bloc.partition("\n")
        morceaux += [MorceauPrepare(m, section=titre.strip()) for m in decouper(corps)]
    return morceaux


def _vectoriser(
    morceaux: Sequence[MorceauPrepare], embeddings: EmbeddingProvider
) -> list[list[float]]:
    if embeddings.dimension != DIMENSION_EMBEDDING:
        raise ValueError(
            f"Dimension d'embedding {embeddings.dimension} ≠ {DIMENSION_EMBEDDING} attendue."
        )
    if not morceaux:
        return []
    return embeddings.vectoriser([m.texte_a_vectoriser for m in morceaux], "document")


def indexer_reglement(session: Session, embeddings: EmbeddingProvider, texte: str) -> int:
    """(Ré)indexe le règlement si son texte ou le modèle a changé ; renvoie le nombre ajouté."""
    morceaux = preparer_reglement(texte)
    existants = session.scalars(
        select(Morceau.texte)
        .where(
            Morceau.source == SourceMorceau.REGLEMENT,
            Morceau.modele_embedding == embeddings.nom_modele,
        )
        .order_by(Morceau.id)
    ).all()
    if list(existants) == [m.texte for m in morceaux]:
        return 0
    session.execute(delete(Morceau).where(Morceau.source == SourceMorceau.REGLEMENT))
    for morceau, vecteur in zip(morceaux, _vectoriser(morceaux, embeddings), strict=True):
        session.add(
            Morceau(
                source=SourceMorceau.REGLEMENT,
                section=morceau.section,
                texte=morceau.texte,
                modele_embedding=embeddings.nom_modele,
                embedding=vecteur,
            )
        )
    session.flush()
    logger.info(
        "Règlement indexé", extra={"etape": "INDEXE", "statut": f"{len(morceaux)} morceaux"}
    )
    return len(morceaux)


def indexer_reglement_fichier(session: Session, embeddings: EmbeddingProvider, chemin: Path) -> int:
    """Indexe le règlement depuis son fichier Markdown."""
    return indexer_reglement(session, embeddings, chemin.read_text(encoding="utf-8"))


def preparer_dossier(dossier: Dossier) -> list[MorceauPrepare]:
    """Morceaux des pages non sensibles d'un dossier, avec page et type de pièce."""
    morceaux: list[MorceauPrepare] = []
    for page in dossier.pages:
        if page.sensible or not page.texte:
            continue
        section = LIBELLES_PIECES.get(page.type_piece) if page.type_piece else None
        morceaux += [
            MorceauPrepare(m, section=section, page=page.numero, type_piece=page.type_piece)
            for m in decouper(page.texte)
        ]
    return morceaux


def indexer_dossier(session: Session, dossier: Dossier, embeddings: EmbeddingProvider) -> int:
    """Remplace les morceaux du dossier ; renvoie le nombre de morceaux indexés."""
    session.execute(delete(Morceau).where(Morceau.dossier_id == dossier.id))
    morceaux = preparer_dossier(dossier)
    for morceau, vecteur in zip(morceaux, _vectoriser(morceaux, embeddings), strict=True):
        session.add(
            Morceau(
                source=SourceMorceau.DOSSIER,
                dossier_id=dossier.id,
                type_piece=morceau.type_piece,
                page=morceau.page,
                section=morceau.section,
                texte=morceau.texte,
                modele_embedding=embeddings.nom_modele,
                embedding=vecteur,
            )
        )
    session.flush()
    logger.info(
        "Dossier indexé",
        extra={
            "dossier_id": str(dossier.id),
            "etape": "INDEXE",
            "statut": f"{len(morceaux)} morceaux",
        },
    )
    return len(morceaux)
