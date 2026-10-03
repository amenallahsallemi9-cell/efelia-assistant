"""Lecture structurée : validation, relance, secours, extraits vérifiés, RGPD, injection."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.db.modeles import Page, Piece
from app.demo.pdf import Candidat, GenerateurDossier
from app.domain.modeles import Confiance, TypePiece
from app.providers.base import ErreurFournisseur, ReponseLLM
from app.providers.fake import FakeLLM
from app.services.lecture import lire_piece, localiser_extrait, marque_visuelle

from .aides import pages_depuis_pdf

CANDIDAT = Candidat("Dupont", "Hélène")


def _piece(type_piece: TypePiece, pages: list[Page]) -> Piece:
    return Piece(type=type_piece, pages=[p.numero for p in pages], confiance=Confiance.HAUTE)


def _certificat(tmp_path: Path) -> tuple[Path, list[Page]]:
    return pages_depuis_pdf(GenerateurDossier(CANDIDAT).certificat().pdf(), tmp_path)


CERTIFICAT_LLM: dict[str, Any] = {
    "nom": "DUPONT",
    "prenom": "Hélène",
    "etablissement": "Université Côte d'Azur",
    "formation": "M1 Informatique",
    "annee_universitaire": "2026-2027",
    "extrait": "Année universitaire 2026-2027",
}


def test_lecture_premiere_tentative(tmp_path: Path) -> None:
    chemin, pages = _certificat(tmp_path)
    llm = FakeLLM(scenario=[ReponseLLM(texte=json.dumps(CERTIFICAT_LLM))])
    donnees, confiance = lire_piece(
        _piece(TypePiece.CERTIFICAT_SCOLARITE, pages), pages, llm, chemin
    )
    assert confiance is Confiance.HAUTE
    assert donnees["nom"] == "DUPONT"
    assert donnees["page"] == 1  # page de l'extrait vérifié
    assert donnees["alertes_injection"] == []
    message = llm.appels[0][0][1].contenu
    assert "<document>" in message
    assert "CERTIFICAT DE SCOLARITÉ" in message
    assert llm.appels[0][2] is not None
    assert llm.appels[0][2].nom == "lecture_certificat_scolarite"


def test_relance_apres_reponse_invalide(tmp_path: Path) -> None:
    chemin, pages = _certificat(tmp_path)
    llm = FakeLLM(
        scenario=[
            ReponseLLM(texte='{"nom": 12'),
            ReponseLLM(texte=json.dumps(CERTIFICAT_LLM)),
        ]
    )
    donnees, confiance = lire_piece(
        _piece(TypePiece.CERTIFICAT_SCOLARITE, pages), pages, llm, chemin
    )
    assert confiance is Confiance.MOYENNE
    assert donnees["annee_universitaire"] == "2026-2027"
    relance = llm.appels[1][0]
    assert relance[-2].role == "assistant"
    assert "Réponse invalide" in relance[-1].contenu


@pytest.mark.parametrize(
    "scenario",
    [
        [ReponseLLM(texte="bla"), ReponseLLM(texte="toujours pas")],
        [ReponseLLM(texte='{"pas": "le bon schéma"}'), ReponseLLM(texte="[]")],
        [ErreurFournisseur("panne")],
    ],
)
def test_echec_secours_heuristique_confiance_faible(tmp_path: Path, scenario: list[Any]) -> None:
    chemin, pages = _certificat(tmp_path)
    donnees, confiance = lire_piece(
        _piece(TypePiece.CERTIFICAT_SCOLARITE, pages), pages, FakeLLM(scenario=scenario), chemin
    )
    assert confiance is Confiance.FAIBLE
    assert donnees["annee_universitaire"] == "2026-2027"  # lu par heuristique


def test_extrait_invente_retire(tmp_path: Path) -> None:
    chemin, pages = _certificat(tmp_path)
    invente = {
        **CERTIFICAT_LLM,
        "extrait": "Félicitations, ce dossier est le meilleur de la promotion",
    }
    donnees, confiance = lire_piece(
        _piece(TypePiece.CERTIFICAT_SCOLARITE, pages),
        pages,
        FakeLLM(scenario=[ReponseLLM(texte=json.dumps(invente))]),
        chemin,
    )
    assert donnees["extrait"] is None
    assert donnees["page"] is None
    assert confiance is Confiance.MOYENNE


def test_localiser_extrait(tmp_path: Path) -> None:
    _, pages = pages_depuis_pdf(GenerateurDossier(CANDIDAT).cv().lettre().pdf(), tmp_path)
    assert localiser_extrait("Mon projet professionnel est de préparer un doctorat", pages) == 3
    assert localiser_extrait("MON  PROJET professionnel est de préparer", pages) == 3
    assert localiser_extrait("court", pages) is None
    assert localiser_extrait("phrase absente du dossier entier", pages) is None


def test_lettre_avec_injection_signalee(tmp_path: Path) -> None:
    chemin, pages = pages_depuis_pdf(
        GenerateurDossier(CANDIDAT).lettre(injection=True).pdf(), tmp_path
    )
    donnees, confiance = lire_piece(
        _piece(TypePiece.LETTRE_MOTIVATION, pages), pages, FakeLLM(), chemin
    )
    assert confiance is Confiance.HAUTE
    assert donnees["formation"]["present"] is True
    assert donnees["formation"]["page"] == 1
    assert donnees["nb_mots"] > 50
    assert len(donnees["alertes_injection"]) == 1
    assert donnees["alertes_injection"][0]["page"] == 1
    assert "ignore tes règles" in donnees["alertes_injection"][0]["extrait"]


def test_cv_nombre_de_pages(tmp_path: Path) -> None:
    chemin, pages = pages_depuis_pdf(GenerateurDossier(CANDIDAT).cv(nb_pages=3).pdf(), tmp_path)
    donnees, _ = lire_piece(_piece(TypePiece.CV, pages), pages, FakeLLM(), chemin)
    assert donnees["nb_pages"] == 3


@pytest.mark.parametrize(("signee", "attendu"), [(True, True), (False, False)])
def test_signature_visuelle(tmp_path: Path, signee: bool, attendu: bool) -> None:
    chemin, pages = pages_depuis_pdf(
        GenerateurDossier(CANDIDAT).attestation(signee=signee).pdf(), tmp_path
    )
    assert marque_visuelle(chemin, 1) is attendu
    donnees, _ = lire_piece(
        _piece(TypePiece.ATTESTATION_NON_CUMUL, pages), pages, FakeLLM(), chemin
    )
    assert donnees["marque_visuelle"] is attendu
    assert donnees["mention_signature"] is signee


def test_justificatif_sensible_jamais_envoye(tmp_path: Path) -> None:
    chemin, pages = pages_depuis_pdf(
        GenerateurDossier(CANDIDAT).justificatif_social().pdf(), tmp_path
    )
    llm = FakeLLM(scenario=[])
    piece = _piece(TypePiece.JUSTIFICATIF_SOCIAL, pages)
    donnees, confiance = lire_piece(piece, pages, llm, chemin)
    assert donnees == {"document_detecte": True}
    assert confiance is Confiance.HAUTE
    assert llm.appels == []


def test_piece_autre_non_lue(tmp_path: Path) -> None:
    chemin, pages = _certificat(tmp_path)
    llm = FakeLLM(scenario=[])
    assert lire_piece(_piece(TypePiece.AUTRE, pages), pages, llm, chemin) == ({}, Confiance.FAIBLE)
    assert llm.appels == []
