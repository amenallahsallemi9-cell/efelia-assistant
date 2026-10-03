"""Les 4 conditions d'éligibilité (→ NON_RECEVABLE si l'une manque)."""

from dataclasses import replace

import pytest

from app.domain.modeles import Verdict
from app.domain.regles import (
    Consequence,
    Fiche,
    Reglement,
    Resultat,
    bourse_est_compatible,
    calculer_statut,
    verifier_eligibilite,
)


def _par_code(fiche: Fiche, reglement: Reglement) -> dict[str, Resultat]:
    return {c.code: c.resultat for c in verifier_eligibilite(fiche, reglement)}


def test_fiche_eligible(fiche: Fiche, reglement: Reglement) -> None:
    controles = verifier_eligibilite(fiche, reglement)
    assert len(controles) == 4
    assert all(c.resultat is Resultat.CONFORME for c in controles)
    assert all(c.consequence is Consequence.NON_RECEVABLE for c in controles)
    assert calculer_statut(controles) is Verdict.RECEVABLE


@pytest.mark.parametrize(
    ("heures", "eligible"),
    [(0, False), (23, False), (24, True), (25, True), (300, True)],
)
def test_seuil_24_heures_inclus(
    fiche: Fiche, reglement: Reglement, heures: int, eligible: bool
) -> None:
    resultat = _par_code(replace(fiche, heures_ia=heures), reglement)["eligibilite_heures_ia"]
    assert resultat is (Resultat.CONFORME if eligible else Resultat.NON_CONFORME)


def test_heures_negatives_refusees(fiche: Fiche) -> None:
    with pytest.raises(ValueError, match="négatif"):
        replace(fiche, heures_ia=-1)


def test_message_heures_insuffisantes(fiche: Fiche, reglement: Reglement) -> None:
    controle = verifier_eligibilite(replace(fiche, heures_ia=20), reglement)[1]
    assert "20 h" in controle.message
    assert "24" in controle.message
    assert controle.preuves[0].source == "fiche"


def test_non_inscrit_uca(fiche: Fiche, reglement: Reglement) -> None:
    controles = verifier_eligibilite(replace(fiche, inscrit_uca=False), reglement)
    assert controles[0].resultat is Resultat.NON_CONFORME
    assert calculer_statut(controles) is Verdict.NON_RECEVABLE


def test_inscription_non_requise_si_reglement_le_permet(fiche: Fiche, reglement: Reglement) -> None:
    souple = replace(reglement, inscription_uca_requise=False)
    resultat = _par_code(replace(fiche, inscrit_uca=False), souple)
    assert resultat["eligibilite_inscription_uca"] is Resultat.CONFORME


def test_alternance_exclue(fiche: Fiche, reglement: Reglement) -> None:
    controles = verifier_eligibilite(replace(fiche, alternance=True), reglement)
    assert (
        _par_code(replace(fiche, alternance=True), reglement)["eligibilite_alternance"]
        is Resultat.NON_CONFORME
    )
    assert calculer_statut(controles) is Verdict.NON_RECEVABLE


@pytest.mark.parametrize(
    "libelle",
    [
        "Bourse CROUS sur critères sociaux",
        "bourse du crous sur criteres sociaux",
        "CROUS - échelon 5",
        "Bourse sociale du CROUS",
        "BCS",
    ],
)
def test_bourse_crous_compatible(fiche: Fiche, reglement: Reglement, libelle: str) -> None:
    assert bourse_est_compatible(libelle, reglement)
    declaree = replace(fiche, autre_bourse=True, autre_bourse_libelle=libelle)
    controles = verifier_eligibilite(declaree, reglement)
    assert controles[3].resultat is Resultat.CONFORME
    assert "compatible" in controles[3].message
    assert calculer_statut(controles) is Verdict.RECEVABLE


@pytest.mark.parametrize(
    "libelle",
    [
        "Aide au mérite CROUS",
        "Bourse Erasmus+",
        "Bourse de mobilité Région Sud",
        "Bourse d'excellence Eiffel",
        None,
    ],
)
def test_autre_bourse_incompatible(fiche: Fiche, reglement: Reglement, libelle: str | None) -> None:
    declaree = replace(fiche, autre_bourse=True, autre_bourse_libelle=libelle)
    controles = verifier_eligibilite(declaree, reglement)
    assert controles[3].resultat is Resultat.NON_CONFORME
    assert reglement.email_envoi in controles[3].message
    assert calculer_statut(controles) is Verdict.NON_RECEVABLE


def test_libelle_ignore_si_aucune_bourse(fiche: Fiche, reglement: Reglement) -> None:
    sans = replace(fiche, autre_bourse=False, autre_bourse_libelle="Erasmus+")
    assert _par_code(sans, reglement)["eligibilite_autre_bourse"] is Resultat.CONFORME


def test_plusieurs_conditions_manquantes(fiche: Fiche, reglement: Reglement) -> None:
    mauvaise = replace(fiche, heures_ia=10, alternance=True, inscrit_uca=False)
    non_conformes = [
        c for c in verifier_eligibilite(mauvaise, reglement) if c.resultat is Resultat.NON_CONFORME
    ]
    assert len(non_conformes) == 3
