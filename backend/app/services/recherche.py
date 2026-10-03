"""Recherche hybride : vecteurs (pgvector, cosinus) + mots-clés (texte intégral français),
fusion par rang réciproque (RRF), puis reranking.

La recherche vectorielle capte le sens (« quand faut-il envoyer ? » ↔ « date limite »),
la recherche plein texte les termes exacts (« ECTS », un nom propre). La fusion RRF ne
dépend que des rangs, pas des échelles de score. Le reranker affine l'ordre final ; s'il
échoue, l'ordre de la fusion est conservé.
"""

import logging
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from app.db.modeles import Morceau
from app.domain.modeles import SourceMorceau, TypePiece
from app.domain.noms import normaliser
from app.providers import Fournisseurs
from app.providers.base import ErreurFournisseur

logger = logging.getLogger(__name__)

CONSTANTE_RRF = 60
NB_CANDIDATS = 20
EF_SEARCH = 100


@dataclass(frozen=True)
class Resultat:
    """Passage trouvé, avec de quoi le citer."""

    morceau_id: int
    texte: str
    source: SourceMorceau
    page: int | None
    type_piece: TypePiece | None
    section: str | None
    score: float


def _filtres(
    requete: Select[tuple[Morceau]],
    source: SourceMorceau,
    modele: str,
    dossier_id: uuid.UUID | None,
) -> Select[tuple[Morceau]]:
    requete = requete.where(Morceau.source == source, Morceau.modele_embedding == modele)
    if source is SourceMorceau.DOSSIER:
        if dossier_id is None:
            raise ValueError("Une recherche dans un dossier exige son identifiant.")
        requete = requete.where(Morceau.dossier_id == dossier_id)
    return requete


def requete_plein_texte(question: str) -> str | None:
    """Requête `to_tsquery` en OU entre les mots utiles, avec et sans accents.

    Seuls des mots alphanumériques sont gardés : aucun opérateur de l'utilisateur ne
    peut atteindre `to_tsquery`.
    """
    mots = re.findall(r"\w{3,}", question.casefold())
    variantes = [v for mot in mots for v in (mot, normaliser(mot)) if v.isalnum()]
    return " | ".join(dict.fromkeys(variantes)) or None


def _par_vecteurs(
    session: Session,
    vecteur: list[float],
    source: SourceMorceau,
    modele: str,
    dossier_id: uuid.UUID | None,
) -> list[Morceau]:
    # Avec un filtre (dossier, modèle), le parcours itératif de pgvector ≥ 0.8 évite de
    # renvoyer moins de résultats que demandé.
    session.execute(text(f"SET LOCAL hnsw.ef_search = {EF_SEARCH}"))
    session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    requete = _filtres(select(Morceau), source, modele, dossier_id)
    distance = Morceau.embedding.cosine_distance(vecteur)
    return list(session.scalars(requete.order_by(distance).limit(NB_CANDIDATS)))


def _par_mots_cles(
    session: Session,
    question: str,
    source: SourceMorceau,
    modele: str,
    dossier_id: uuid.UUID | None,
) -> list[Morceau]:
    expression = requete_plein_texte(question)
    if expression is None:
        return []
    tsquery = func.to_tsquery("french", expression)
    requete = _filtres(select(Morceau), source, modele, dossier_id).where(
        Morceau.tsv.bool_op("@@")(tsquery)
    )
    rang = func.ts_rank(Morceau.tsv, tsquery)
    return list(session.scalars(requete.order_by(rang.desc()).limit(NB_CANDIDATS)))


def fusion_rrf(*classements: list[Morceau]) -> list[tuple[Morceau, float]]:
    """Fusion par rang réciproque : score = Σ 1 / (60 + rang)."""
    scores: dict[int, float] = {}
    morceaux: dict[int, Morceau] = {}
    for classement in classements:
        for rang, morceau in enumerate(classement, start=1):
            scores[morceau.id] = scores.get(morceau.id, 0.0) + 1 / (CONSTANTE_RRF + rang)
            morceaux[morceau.id] = morceau
    ordre = sorted(scores, key=lambda i: (-scores[i], i))
    return [(morceaux[i], scores[i]) for i in ordre]


def _resultat(morceau: Morceau, score: float) -> Resultat:
    return Resultat(
        morceau_id=morceau.id,
        texte=morceau.texte,
        source=morceau.source,
        page=morceau.page,
        type_piece=morceau.type_piece,
        section=morceau.section,
        score=round(score, 4),
    )


def rechercher(
    session: Session,
    fournisseurs: Fournisseurs,
    question: str,
    source: SourceMorceau,
    dossier_id: uuid.UUID | None = None,
    k: int = 3,
) -> list[Resultat]:
    """Les `k` passages les plus pertinents pour la question."""
    question = " ".join(question.split())
    if not question:
        return []
    modele = fournisseurs.embeddings.nom_modele
    [vecteur] = fournisseurs.embeddings.vectoriser([question], "requete")
    candidats = fusion_rrf(
        _par_vecteurs(session, vecteur, source, modele, dossier_id),
        _par_mots_cles(session, question, source, modele, dossier_id),
    )[:NB_CANDIDATS]
    if not candidats:
        return []
    try:
        # Même texte enrichi (section + passage) que pour les embeddings.
        documents = [f"{m.section} — {m.texte}" if m.section else m.texte for m, _ in candidats]
        ordre = fournisseurs.reranker.reordonner(question, documents, k)
    except ErreurFournisseur as exc:
        logger.warning("Reranking indisponible, ordre de la fusion conservé", exc_info=exc)
        return [_resultat(m, s) for m, s in candidats[:k]]
    return [_resultat(candidats[i][0], score) for i, score in ordre if 0 <= i < len(candidats)]


def nettoyer_question(question: str, longueur_max: int = 500) -> str:
    """Question réduite à une longueur raisonnable, sans caractères de contrôle."""
    return re.sub(r"[\x00-\x1f]", " ", question)[:longueur_max].strip()
