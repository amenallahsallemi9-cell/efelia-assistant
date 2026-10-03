"""Fixtures du domaine : règlement réel 2026, fiche et faits d'un dossier complet."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.core.reglement import charger_reglement
from app.domain.coherence import (
    DonneesAttestation,
    DonneesCertificat,
    DonneesLettre,
    DonneesReleve,
    FaitsCoherence,
    ThemeLettre,
)
from app.domain.modeles import TypePiece
from app.domain.regles import FaitsPieces, Fiche, Reglement

CHEMIN_REGLEMENT = Path(__file__).resolve().parents[4] / "config" / "regles_2026.yaml"
PARIS = ZoneInfo("Europe/Paris")


@pytest.fixture(scope="session")
def reglement() -> Reglement:
    """Le vrai règlement versionné : les tests vérifient aussi le fichier de configuration."""
    return charger_reglement(CHEMIN_REGLEMENT)


@pytest.fixture
def fiche() -> Fiche:
    return Fiche(
        nom="Dupont",
        prenom="Hélène",
        inscrit_uca=True,
        heures_ia=48,
        alternance=False,
        autre_bourse=False,
        formation="M1 Informatique",
    )


@pytest.fixture
def date_ok() -> datetime:
    return datetime(2026, 10, 10, 14, 0, tzinfo=PARIS)


@pytest.fixture
def pieces_completes() -> FaitsPieces:
    return FaitsPieces(
        pages={
            TypePiece.CERTIFICAT_SCOLARITE: (1,),
            TypePiece.CV: (2, 3),
            TypePiece.RELEVE_NOTES: (4,),
            TypePiece.LETTRE_MOTIVATION: (5,),
            TypePiece.ATTESTATION_NON_CUMUL: (6,),
        },
        cv_nb_pages=2,
        attestation_signee=True,
        attestation_extrait="Fait à Nice, le 1er octobre 2026",
    )


@pytest.fixture
def coherence_ok() -> FaitsCoherence:
    return FaitsCoherence(
        certificat=DonneesCertificat(
            nom="DUPONT",
            prenom="Helene",
            etablissement="Université Côte d'Azur",
            annee_universitaire="2026-2027",
            page=1,
            extrait="Mme DUPONT Helene est inscrite pour l'année 2026-2027",
        ),
        lettre=DonneesLettre(
            themes={
                "formation": ThemeLettre(True, "en M1 Informatique", 5),
                "parcours": ThemeLettre(True, "après une licence", 5),
                "projet": ThemeLettre(True, "je souhaite devenir chercheuse", 5),
            },
            page=5,
        ),
        releve=DonneesReleve(annee="2025-2026", page=4),
        attestation=DonneesAttestation(bourse_declaree=None, page=6),
    )
