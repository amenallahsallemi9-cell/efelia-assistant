"""Indexation pgvector et recherche hybride (mode démo : embeddings par hachage)."""

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.db.modeles import Dossier, Morceau
from app.demo import pdf as demo
from app.domain.modeles import SourceMorceau, TypePiece
from app.domain.regles import Reglement
from app.providers import Fournisseurs, construire_fournisseurs
from app.providers.base import ErreurFournisseur
from app.providers.fake import FakeEmbeddings, FakeLLM, FakeReranker
from app.schemas import FicheDeclaree
from app.services.depot import creer_dossier
from app.services.indexation import indexer_dossier, indexer_reglement_fichier
from app.services.recherche import fusion_rrf, rechercher
from app.workers.pipeline import PublieurNul, executer_pipeline

FICHE = {
    "nom": "Dupont",
    "prenom": "Hélène",
    "email": "h@etu.fr",
    "formation": "M1",
    "inscrit_uca": True,
    "heures_ia": 48,
    "alternance": False,
    "autre_bourse": False,
}


@pytest.fixture
def fournisseurs(parametres_test: Parametres) -> Fournisseurs:
    return construire_fournisseurs(parametres_test)


def _dossier(
    session: Session, parametres: Parametres, reglement: Reglement, contenu: bytes, nom: str
) -> Dossier:
    dossier = creer_dossier(
        session,
        FicheDeclaree.model_validate({**FICHE, "nom": nom}),
        "x.pdf",
        contenu,
        parametres,
        reglement,
    )
    executer_pipeline(session, dossier.id, parametres, PublieurNul(), ocr=lambda _: "")
    session.refresh(dossier)
    return dossier


@pytest.fixture
def dossier(session_test: Session, parametres_test: Parametres, reglement: Reglement) -> Dossier:
    contenu = demo.dossier_avec_justificatifs(demo.Candidat("Dupont", "Hélène"))
    return _dossier(session_test, parametres_test, reglement, contenu, "Dupont")


def test_pipeline_indexe_dossier_et_reglement(session_test: Session, dossier: Dossier) -> None:
    morceaux = session_test.scalars(select(Morceau).where(Morceau.dossier_id == dossier.id)).all()
    assert morceaux
    assert {m.modele_embedding for m in morceaux} == {"fake-embeddings"}
    assert all(len(m.embedding) == 1024 for m in morceaux)
    # RGPD : aucun justificatif sensible indexé
    assert not {m.page for m in morceaux} & {8, 9}
    assert not any("Revenu fiscal" in m.texte for m in morceaux)
    assert session_test.scalar(
        select(func.count()).where(Morceau.source == SourceMorceau.REGLEMENT)
    )


def test_reindexation_idempotente(
    session_test: Session,
    dossier: Dossier,
    fournisseurs: Fournisseurs,
    parametres_test: Parametres,
) -> None:
    avant = session_test.scalar(select(func.count()).select_from(Morceau))
    assert (
        indexer_reglement_fichier(
            session_test, fournisseurs.embeddings, parametres_test.reglement_texte
        )
        == 0
    )
    indexer_dossier(session_test, dossier, fournisseurs.embeddings)
    assert session_test.scalar(select(func.count()).select_from(Morceau)) == avant


@pytest.mark.parametrize(
    ("question", "attendu"),
    [
        ("Quelle est la date limite d'envoi ?", "18 octobre 2026"),
        ("La bourse CROUS est-elle cumulable ?", "CROUS sur critères sociaux est compatible"),
        ("Combien de pages pour le CV ?", "2 pages maximum"),
        ("Montant de la bourse et versement", "10 000 euros"),
    ],
)
def test_rag_reglement(
    session_test: Session,
    dossier: Dossier,
    fournisseurs: Fournisseurs,
    question: str,
    attendu: str,
) -> None:
    resultats = rechercher(session_test, fournisseurs, question, SourceMorceau.REGLEMENT, k=3)
    assert 1 <= len(resultats) <= 3
    assert any(attendu in r.texte for r in resultats)
    assert all(r.source is SourceMorceau.REGLEMENT and r.section for r in resultats)


def test_rag_dossier_avec_page(
    session_test: Session, dossier: Dossier, fournisseurs: Fournisseurs
) -> None:
    resultats = rechercher(
        session_test,
        fournisseurs,
        "projet professionnel doctorat",
        SourceMorceau.DOSSIER,
        dossier.id,
    )
    meilleur = resultats[0]
    assert meilleur.type_piece is TypePiece.LETTRE_MOTIVATION
    assert meilleur.page == 5
    assert "doctorat" in meilleur.texte


def test_mot_exact_par_plein_texte(
    session_test: Session, dossier: Dossier, fournisseurs: Fournisseurs
) -> None:
    resultats = rechercher(session_test, fournisseurs, "ECTS", SourceMorceau.DOSSIER, dossier.id)
    assert resultats[0].type_piece is TypePiece.RELEVE_NOTES


def test_isolation_entre_dossiers(
    session_test: Session,
    parametres_test: Parametres,
    reglement: Reglement,
    dossier: Dossier,
    fournisseurs: Fournisseurs,
) -> None:
    autre = _dossier(
        session_test,
        parametres_test,
        reglement,
        demo.dossier_complet(demo.Candidat("Martin", "Zoé")),
        "Martin",
    )
    resultats = rechercher(
        session_test, fournisseurs, "MARTIN Zoé", SourceMorceau.DOSSIER, dossier.id, k=10
    )
    ids = set(session_test.scalars(select(Morceau.id).where(Morceau.dossier_id == dossier.id)))
    assert {r.morceau_id for r in resultats} <= ids
    assert autre.id != dossier.id


def test_autre_modele_ignore(
    session_test: Session, dossier: Dossier, fournisseurs: Fournisseurs
) -> None:
    class AutresEmbeddings(FakeEmbeddings):
        nom_modele = "autre-modele"

    autres = Fournisseurs(FakeLLM(), AutresEmbeddings(), FakeReranker())
    assert rechercher(session_test, autres, "projet", SourceMorceau.DOSSIER, dossier.id) == []


def test_reranker_en_panne(
    session_test: Session, dossier: Dossier, fournisseurs: Fournisseurs
) -> None:
    class RerankerEnPanne(FakeReranker):
        def reordonner(self, *args: Any, **kwargs: Any) -> list[tuple[int, float]]:
            raise ErreurFournisseur("panne")

    secours = Fournisseurs(fournisseurs.llm, fournisseurs.embeddings, RerankerEnPanne())
    resultats = rechercher(session_test, secours, "date limite", SourceMorceau.REGLEMENT, k=2)
    assert len(resultats) == 2


def test_cas_limites(session_test: Session, dossier: Dossier, fournisseurs: Fournisseurs) -> None:
    assert rechercher(session_test, fournisseurs, "   ", SourceMorceau.REGLEMENT) == []
    assert rechercher(session_test, fournisseurs, "x", SourceMorceau.DOSSIER, uuid.uuid4()) == []
    with pytest.raises(ValueError, match="identifiant"):
        rechercher(session_test, fournisseurs, "x", SourceMorceau.DOSSIER)


def test_fusion_rrf() -> None:
    a, b, c = (Morceau(id=i, texte=str(i)) for i in (1, 2, 3))
    fusion = fusion_rrf([a, b], [b, c])
    assert [m.id for m, _ in fusion] == [2, 1, 3]
    assert fusion[0][1] == pytest.approx(1 / 62 + 1 / 61)


def test_index_hnsw_utilisable(session_test: Session, dossier: Dossier) -> None:
    """L'index HNSW est valide pour l'opérateur cosinus (tri pur, parcours séquentiel interdit).

    Avec des filtres sélectifs (un dossier), Postgres peut préférer les index B-tree :
    c'est voulu, l'index HNSW sert les recherches sur de gros volumes.
    """
    from sqlalchemy import text

    vecteur = FakeEmbeddings().vectoriser(["projet"], "requete")[0]
    session_test.execute(text("SET LOCAL enable_seqscan = off"))
    requete = select(Morceau.id).order_by(Morceau.embedding.cosine_distance(vecteur)).limit(5)
    compilee = requete.compile(session_test.get_bind(), compile_kwargs={"literal_binds": True})
    plan = "\n".join(session_test.execute(text(f"EXPLAIN {compilee}")).scalars())
    assert "ix_morceaux_embedding_hnsw" in plan
