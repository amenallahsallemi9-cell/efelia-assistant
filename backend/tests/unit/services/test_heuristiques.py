"""Classification et lecture sans LLM (secours et mode démo)."""

from pathlib import Path

import pytest

from app.demo.pdf import Candidat, GenerateurDossier, dossier_avec_justificatifs
from app.domain.modeles import TypePiece
from app.services.heuristiques import classer_par_mots_cles, lire_par_heuristique

from .aides import pages_depuis_pdf

CANDIDAT = Candidat("Dupont", "Hélène")


def test_classement_des_pages_generees(tmp_path: Path) -> None:
    _, pages = pages_depuis_pdf(dossier_avec_justificatifs(CANDIDAT), tmp_path)
    types = [classer_par_mots_cles(p.texte)[0] if p.texte else p.type_piece for p in pages]
    assert types == [
        TypePiece.CERTIFICAT_SCOLARITE,
        TypePiece.CV,
        TypePiece.CV,
        TypePiece.RELEVE_NOTES,
        TypePiece.LETTRE_MOTIVATION,
        TypePiece.ATTESTATION_NON_CUMUL,
        TypePiece.LETTRE_RECOMMANDATION,
        TypePiece.JUSTIFICATIF_SOCIAL,
        TypePiece.JUSTIFICATIF_HANDICAP,
    ]


@pytest.mark.parametrize("texte", ["", "Recette : 200 g de farine", "Page 3"])
def test_page_inclassable(texte: str) -> None:
    assert classer_par_mots_cles(texte) == (TypePiece.AUTRE, 0.3)


def _texte(tmp_path: Path, generateur: GenerateurDossier) -> str:
    _, pages = pages_depuis_pdf(generateur.pdf(), tmp_path)
    return "\n".join(p.texte or "" for p in pages)


def test_lecture_certificat(tmp_path: Path) -> None:
    donnees = lire_par_heuristique(
        TypePiece.CERTIFICAT_SCOLARITE, _texte(tmp_path, GenerateurDossier(CANDIDAT).certificat())
    )
    assert donnees["nom"] == "DUPONT"
    assert donnees["prenom"] == "Hélène"
    assert donnees["etablissement"] == "Université Côte d'Azur"
    assert donnees["annee_universitaire"] == "2026-2027"
    assert "inscrit" in donnees["extrait"]


def test_lecture_cv(tmp_path: Path) -> None:
    donnees = lire_par_heuristique(TypePiece.CV, _texte(tmp_path, GenerateurDossier(CANDIDAT).cv()))
    assert "PyTorch" in donnees["competences"]
    assert any("anomalies" in p for p in donnees["projets"])
    assert any("I3S" in e for e in donnees["experiences"])
    assert "github.com/hélènedupont" in donnees["liens"]


def test_lecture_releve(tmp_path: Path) -> None:
    donnees = lire_par_heuristique(
        TypePiece.RELEVE_NOTES, _texte(tmp_path, GenerateurDossier(CANDIDAT).releve())
    )
    assert donnees == {
        "annee": "2025-2026",
        "moyenne_generale": 16.2,
        "mention": "Très bien",
        "credits_ects": 60,
        "extrait": donnees["extrait"],
    }


def test_lecture_lettre(tmp_path: Path) -> None:
    complete = lire_par_heuristique(
        TypePiece.LETTRE_MOTIVATION, _texte(tmp_path, GenerateurDossier(CANDIDAT).lettre())
    )
    assert all(complete[t]["present"] for t in ("formation", "parcours", "projet"))
    assert complete["mentionne_ia"] is True
    partielle = lire_par_heuristique(
        TypePiece.LETTRE_MOTIVATION,
        _texte(tmp_path, GenerateurDossier(CANDIDAT).lettre(parcours=False, projet=False)),
    )
    assert partielle["formation"]["present"] is True
    assert partielle["projet"] == {"present": False, "extrait": None}


def test_lecture_attestation(tmp_path: Path) -> None:
    signee = lire_par_heuristique(
        TypePiece.ATTESTATION_NON_CUMUL, _texte(tmp_path, GenerateurDossier(CANDIDAT).attestation())
    )
    assert signee["mention_signature"] is True
    assert signee["lieu_date"].startswith("Fait à Nice, le 1er octobre 2026")
    assert signee["bourse_declaree"] is None
    autre = lire_par_heuristique(
        TypePiece.ATTESTATION_NON_CUMUL,
        _texte(tmp_path, GenerateurDossier(CANDIDAT).attestation(signee=False, bourse="Erasmus+")),
    )
    assert autre["mention_signature"] is False
    assert autre["bourse_declaree"] == "Erasmus+"


def test_lecture_recommandation_et_autre(tmp_path: Path) -> None:
    donnees = lire_par_heuristique(
        TypePiece.LETTRE_RECOMMANDATION,
        _texte(tmp_path, GenerateurDossier(CANDIDAT).recommandation()),
    )
    assert donnees["auteur"] == "Pr. Claire Fontaine"
    assert lire_par_heuristique(TypePiece.AUTRE, "x") == {}
