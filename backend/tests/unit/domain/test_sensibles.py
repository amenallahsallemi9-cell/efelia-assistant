"""Détection des justificatifs sensibles, avant tout stockage ou appel au LLM."""

import pytest

from app.domain.modeles import TypePiece
from app.domain.sensibles import detecter_page_sensible


@pytest.mark.parametrize(
    "texte",
    [
        "AVIS D'IMPÔT 2026\nRevenu fiscal de référence : 12 345 €\nNuméro fiscal : 0000",
        "Relevé de compte\nIBAN : FR76 3000 6000 0112 3456 7890 189\nSolde créditeur",
        "BULLETIN DE PAIE — Septembre 2026\nSalaire brut 1 200 €\nNet à payer 950 €",
        "Notification conditionnelle de bourse — Échelon 5",
    ],
)
def test_justificatifs_sociaux(texte: str) -> None:
    detection = detecter_page_sensible(texte)
    assert detection is not None
    assert detection.type_piece is TypePiece.JUSTIFICATIF_SOCIAL
    assert 0.5 < detection.confiance <= 0.95


@pytest.mark.parametrize(
    "texte",
    [
        "Maison départementale des personnes handicapées\nNotification RQTH",
        "Carte mobilité inclusion — mention invalidité",
        "CERTIFICAT MÉDICAL\nJe soussigné, docteur…",
        "Décision : taux d'incapacité compris entre 50 et 79 %",
    ],
)
def test_justificatifs_handicap(texte: str) -> None:
    detection = detecter_page_sensible(texte)
    assert detection is not None
    assert detection.type_piece is TypePiece.JUSTIFICATIF_HANDICAP


@pytest.mark.parametrize(
    "texte",
    [
        "",
        "CURRICULUM VITAE\nBénévole auprès de la MDPH des Alpes-Maritimes",  # indice faible seul
        "LETTRE DE MOTIVATION\nJe suis boursier, échelon 3.",
        "RELEVÉ DE NOTES\nMoyenne générale 16,2",
        # L'attestation de non-cumul mentionne la bourse CROUS mais n'est pas sensible
        "ATTESTATION SUR L'HONNEUR DE NON-CUMUL\nhors bourse CROUS sur critères sociaux, "
        "notification de bourse échelon 5",
    ],
)
def test_pages_ordinaires(texte: str) -> None:
    assert detecter_page_sensible(texte) is None
