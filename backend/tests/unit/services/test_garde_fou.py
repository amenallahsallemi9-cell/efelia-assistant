"""Garde-fous sur la sortie du LLM."""

import pytest

from app.domain.modeles import Verdict
from app.services.agent.garde_fou import (
    appliquer_garde_fou,
    contient_prediction,
    retirer_predictions,
)


@pytest.mark.parametrize(
    ("regles", "propose", "attendu"),
    [
        (Verdict.A_COMPLETER, Verdict.RECEVABLE, (Verdict.A_COMPLETER, True)),
        (Verdict.NON_RECEVABLE, Verdict.A_COMPLETER, (Verdict.NON_RECEVABLE, True)),
        (Verdict.RECEVABLE, Verdict.RECEVABLE, (Verdict.RECEVABLE, False)),
        (Verdict.RECEVABLE, None, (Verdict.RECEVABLE, False)),
    ],
)
def test_statut_des_regles_toujours(
    regles: Verdict, propose: Verdict | None, attendu: tuple[Verdict, bool]
) -> None:
    assert appliquer_garde_fou(regles, propose) == attendu


@pytest.mark.parametrize(
    "phrase",
    [
        "Vous avez de bonnes chances d'obtenir la bourse.",
        "La probabilité de succès est élevée.",
        "Vous serez probablement retenue par le jury.",
        "Le dossier sera sélectionné.",
        "Environ 70 % des dossiers comme le vôtre réussissent.",
        "Vous obtiendrez la bourse.",
        "Ce dossier fait figure de favori.",
    ],
)
def test_predictions_reperees(phrase: str) -> None:
    assert contient_prediction(phrase)


@pytest.mark.parametrize(
    "phrase",
    [
        "Le dossier est complet et peut être examiné par le jury.",
        "Ajoutez votre certificat de scolarité 2026-2027.",
        "Mettez en avant votre projet en IA.",
    ],
)
def test_phrases_neutres(phrase: str) -> None:
    assert not contient_prediction(phrase)


def test_retirer_predictions_conserve_la_structure() -> None:
    texte = (
        "### Points forts\n"
        "- Excellente moyenne. Vos chances sont réelles.\n"
        "- Vous serez retenu.\n"
        "Lettre claire."
    )
    nettoye, nb = retirer_predictions(texte)
    assert nb == 2
    assert nettoye == "### Points forts\n- Excellente moyenne.\nLettre claire."
