"""Format : date limite à la seconde près (heure de Paris) et nom du fichier."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.domain.modeles import Verdict
from app.domain.regles import (
    Consequence,
    Fiche,
    Reglement,
    Resultat,
    calculer_statut,
    verifier_delai,
    verifier_format,
    verifier_nom_fichier,
)

from .conftest import PARIS


def test_borne_exclusive_fin_du_18_octobre(reglement: Reglement) -> None:
    assert reglement.reception_avant == datetime(2026, 10, 19, 0, 0, tzinfo=PARIS)


@pytest.mark.parametrize(
    ("reception", "a_temps"),
    [
        (datetime(2026, 10, 18, 23, 59, 59, tzinfo=PARIS), True),
        (datetime(2026, 10, 18, 23, 59, 59, 999_999, tzinfo=PARIS), True),
        (datetime(2026, 10, 19, 0, 0, 0, tzinfo=PARIS), False),
        (datetime(2026, 10, 19, 0, 0, 1, tzinfo=PARIS), False),
        (datetime(2026, 10, 18, 0, 0, 0, tzinfo=PARIS), True),
        (datetime(2026, 9, 1, 8, 0, tzinfo=PARIS), True),
        (datetime(2026, 11, 2, 8, 0, tzinfo=PARIS), False),
    ],
)
def test_delai_a_la_seconde(reglement: Reglement, reception: datetime, a_temps: bool) -> None:
    controle = verifier_delai(reception, reglement)
    assert controle.resultat is (Resultat.CONFORME if a_temps else Resultat.NON_CONFORME)


@pytest.mark.parametrize(
    ("reception", "a_temps"),
    [
        # En octobre 2026, Paris est en heure d'été (UTC+2) jusqu'au 25 octobre.
        (datetime(2026, 10, 18, 21, 59, 59, tzinfo=UTC), True),
        (datetime(2026, 10, 18, 22, 0, 0, tzinfo=UTC), False),
        (datetime(2026, 10, 18, 17, 30, 0, tzinfo=timezone(timedelta(hours=-4))), True),
        (datetime(2026, 10, 18, 18, 0, 0, tzinfo=timezone(timedelta(hours=-4))), False),
    ],
)
def test_delai_autres_fuseaux(reglement: Reglement, reception: datetime, a_temps: bool) -> None:
    assert (verifier_delai(reception, reglement).resultat is Resultat.CONFORME) is a_temps


def test_delai_message_en_heure_de_paris(reglement: Reglement) -> None:
    controle = verifier_delai(datetime(2026, 10, 18, 22, 0, 0, tzinfo=UTC), reglement)
    assert "19/10/2026 à 00:00:00" in controle.message
    assert "après la date limite" in controle.message
    assert controle.consequence is Consequence.NON_RECEVABLE


def test_hors_delai_non_recevable(fiche: Fiche, reglement: Reglement) -> None:
    controles = verifier_format(
        "BourseExcellence2026_DUPONT.HELENE.pdf",
        datetime(2026, 10, 20, 9, 0, tzinfo=PARIS),
        fiche,
        reglement,
    )
    assert calculer_statut(controles) is Verdict.NON_RECEVABLE


def test_date_sans_fuseau_refusee(reglement: Reglement) -> None:
    with pytest.raises(ValueError, match="fuseau"):
        verifier_delai(datetime(2026, 10, 18, 12, 0), reglement)


def test_reglement_sans_fuseau_refuse(reglement: Reglement) -> None:
    with pytest.raises(ValueError, match="fuseau"):
        replace(reglement, reception_avant=datetime(2026, 10, 19))


def test_nom_fichier_conforme(fiche: Fiche, reglement: Reglement) -> None:
    controle = verifier_nom_fichier("BourseExcellence2026_DUPONT.HELENE.pdf", fiche, reglement)
    assert controle.resultat is Resultat.CONFORME


def test_nom_fichier_non_conforme_simple_avertissement(
    fiche: Fiche, reglement: Reglement, date_ok: datetime
) -> None:
    controles = verifier_format("candidature.pdf", date_ok, fiche, reglement)
    nom = controles[0]
    assert nom.resultat is Resultat.NON_CONFORME
    assert nom.consequence is Consequence.AVERTISSEMENT
    assert nom.est_avertissement
    assert "BourseExcellence2026_DUPONT.HELENE.pdf" in nom.message
    assert calculer_statut(controles) is Verdict.RECEVABLE
