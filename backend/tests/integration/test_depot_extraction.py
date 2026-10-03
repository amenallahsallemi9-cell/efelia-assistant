"""Dépôt d'un dossier puis étape d'extraction du pipeline, sur une vraie base."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.db.modeles import Dossier, Page
from app.demo.pdf import Candidat, dossier_avec_justificatifs, dossier_complet
from app.domain.modeles import MethodeExtraction, StatutPipeline, TypePiece
from app.domain.regles import Reglement
from app.schemas import FicheDeclaree
from app.services.depot import ErreurDepot, creer_dossier
from app.workers.pipeline import ETAPES, Contexte, ErreurEtape, executer_pipeline

CANDIDAT = Candidat("Dupont", "Hélène")
MAINTENANT = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


class PublieurMemoire:
    def __init__(self) -> None:
        self.evenements: list[dict[str, Any]] = []

    def publier(self, dossier_id: uuid.UUID, evenement: dict[str, Any]) -> None:
        self.evenements.append(evenement)


def _fiche(**modifs: Any) -> FicheDeclaree:
    return FicheDeclaree.model_validate(
        {
            "nom": "Dupont",
            "prenom": "Hélène",
            "email": "helene.dupont@etu.univ-cotedazur.fr",
            "formation": "M1 Informatique",
            "inscrit_uca": True,
            "heures_ia": 48,
            "alternance": False,
            "autre_bourse": False,
            **modifs,
        }
    )


def _sans_ocr(_: object) -> str:
    return ""


def test_creer_dossier(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    dossier = creer_dossier(
        session_test,
        _fiche(autre_bourse=True, autre_bourse_libelle="Bourse CROUS échelon 4"),
        "../BourseExcellence2026_DUPONT.HELENE.pdf",
        dossier_complet(CANDIDAT),
        parametres_test,
        reglement,
        maintenant=MAINTENANT,
    )
    assert dossier.statut_pipeline is StatutPipeline.RECU
    assert dossier.nb_pages == 6
    assert dossier.date_reception == MAINTENANT
    assert dossier.nom_fichier == "BourseExcellence2026_DUPONT.HELENE.pdf"
    assert dossier.bourse_crous is True
    chemin = Path(dossier.chemin_fichier)
    assert chemin.parent == parametres_test.stockage_dir
    assert "DUPONT" not in chemin.name  # nom aléatoire


def test_date_envoi_declaree_prioritaire(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    envoi = datetime(2026, 10, 18, 21, 30, tzinfo=UTC)
    dossier = creer_dossier(
        session_test,
        _fiche(date_envoi=envoi.isoformat()),
        "x.pdf",
        dossier_complet(CANDIDAT),
        parametres_test,
        reglement,
        maintenant=MAINTENANT,
    )
    assert dossier.date_reception == envoi


def test_fichier_invalide_rien_n_est_stocke(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    with pytest.raises(ErreurDepot):
        creer_dossier(session_test, _fiche(), "x.pdf", b"pas un pdf", parametres_test, reglement)
    assert session_test.scalars(select(Dossier)).all() == []
    assert not parametres_test.stockage_dir.exists() or not any(
        parametres_test.stockage_dir.iterdir()
    )


def test_pipeline_extraction(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    dossier = creer_dossier(
        session_test,
        _fiche(),
        "x.pdf",
        dossier_avec_justificatifs(CANDIDAT),
        parametres_test,
        reglement,
    )
    publieur = PublieurMemoire()
    statut = executer_pipeline(
        session_test, dossier.id, parametres_test, publieur, etapes=ETAPES[:1], ocr=_sans_ocr
    )
    assert statut is StatutPipeline.EXTRAIT

    pages = session_test.scalars(
        select(Page).where(Page.dossier_id == dossier.id).order_by(Page.numero)
    ).all()
    assert len(pages) == 9
    assert all(p.methode is MethodeExtraction.TEXTE for p in pages)
    sensibles = [p for p in pages if p.sensible]
    assert [p.type_piece for p in sensibles] == [
        TypePiece.JUSTIFICATIF_SOCIAL,
        TypePiece.JUSTIFICATIF_HANDICAP,
    ]
    # RGPD : aucun texte de justificatif sensible n'est stocké
    assert all(p.texte is None for p in sensibles)
    textes = " ".join(p.texte or "" for p in pages)
    assert "Revenu fiscal" not in textes
    assert "incapacité" not in textes

    assert [e["statut"] for e in publieur.evenements] == ["EXTRAIT"]
    assert publieur.evenements[0]["etape"] == "extraction"


def test_pipeline_relance_idempotente(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    dossier = creer_dossier(
        session_test, _fiche(), "x.pdf", dossier_complet(CANDIDAT), parametres_test, reglement
    )
    for _ in range(2):
        executer_pipeline(
            session_test, dossier.id, parametres_test, PublieurMemoire(), ocr=_sans_ocr
        )
    nb = session_test.scalars(select(Page).where(Page.dossier_id == dossier.id)).all()
    assert len(nb) == 6


@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (ErreurEtape("Le PDF est illisible."), "Le PDF est illisible."),
        (RuntimeError("texte sensible du document"), "Erreur inattendue pendant l'étape « test »."),
    ],
)
def test_pipeline_erreur(
    session_test: Session,
    parametres_test: Parametres,
    reglement: Reglement,
    exception: Exception,
    message: str,
) -> None:
    dossier = creer_dossier(
        session_test, _fiche(), "x.pdf", dossier_complet(CANDIDAT), parametres_test, reglement
    )

    def etape_qui_echoue(_: Contexte) -> None:
        raise exception

    publieur = PublieurMemoire()
    statut = executer_pipeline(
        session_test,
        dossier.id,
        parametres_test,
        publieur,
        etapes=[(StatutPipeline.EXTRAIT, "test", etape_qui_echoue)],
    )
    assert statut is StatutPipeline.ERREUR
    session_test.refresh(dossier)
    assert dossier.statut_pipeline is StatutPipeline.ERREUR
    assert dossier.message_erreur == message
    assert publieur.evenements[-1] == {
        **publieur.evenements[-1],
        "statut": "ERREUR",
        "message": message,
    }


def test_pipeline_dossier_inconnu(session_test: Session, parametres_test: Parametres) -> None:
    with pytest.raises(LookupError):
        executer_pipeline(session_test, uuid.uuid4(), parametres_test, PublieurMemoire())
