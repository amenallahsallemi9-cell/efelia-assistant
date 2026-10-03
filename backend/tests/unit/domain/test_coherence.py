"""Contrôles croisés fiche ↔ documents."""

from dataclasses import replace

import pytest

from app.domain.coherence import (
    DonneesAttestation,
    DonneesCertificat,
    DonneesLettre,
    DonneesReleve,
    FaitsCoherence,
    ThemeLettre,
    etablissement_reconnu,
    normaliser_annee,
    verifier_coherence,
)
from app.domain.regles import Consequence, Fiche, Reglement, Resultat


def _controle(fiche: Fiche, faits: FaitsCoherence, reglement: Reglement, code: str):  # type: ignore[no-untyped-def]
    return next(c for c in verifier_coherence(fiche, faits, reglement) if c.code == code)


def test_dossier_coherent(fiche: Fiche, coherence_ok: FaitsCoherence, reglement: Reglement) -> None:
    controles = verifier_coherence(fiche, coherence_ok, reglement)
    assert len(controles) == 6
    assert all(c.resultat is Resultat.CONFORME for c in controles)


def test_aucune_piece_aucun_controle(fiche: Fiche, reglement: Reglement) -> None:
    assert verifier_coherence(fiche, FaitsCoherence(), reglement) == []


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("2026-2027", "2026-2027"),
        ("Année universitaire 2026/2027", "2026-2027"),
        ("2026 – 2027", "2026-2027"),
        ("2026-27", "2026-2027"),
        ("année 2025-2026", "2025-2026"),
        ("le 12/09/2026", None),
        ("", None),
        (None, None),
    ],
)
def test_normaliser_annee(texte: str | None, attendu: str | None) -> None:
    assert normaliser_annee(texte) == attendu


@pytest.mark.parametrize(
    ("etablissement", "reconnu"),
    [
        ("Université Côte d'Azur", True),
        ("UNIVERSITE COTE D'AZUR — UFR Sciences", True),
        ("UCA", True),
        ("Université Côte d’Azur", True),
        ("Université de Nice Sophia Antipolis", False),
        ("Éducation nationale", False),  # « uca » n'est pas un mot entier
        ("Sorbonne Université", False),
    ],
)
def test_etablissement(etablissement: str, reconnu: bool, reglement: Reglement) -> None:
    assert etablissement_reconnu(etablissement, reglement) is reconnu


def test_certificat_au_mauvais_nom(
    fiche: Fiche, coherence_ok: FaitsCoherence, reglement: Reglement
) -> None:
    assert coherence_ok.certificat is not None
    faits = replace(
        coherence_ok, certificat=replace(coherence_ok.certificat, nom="Durand", prenom="Paul")
    )
    controle = _controle(fiche, faits, reglement, "certificat_identite")
    assert controle.resultat is Resultat.NON_CONFORME
    assert controle.consequence is Consequence.A_COMPLETER
    assert "Paul Durand" in controle.message
    assert controle.preuves[0].page == 1
    assert controle.preuves[0].extrait


def test_certificat_prenoms_dans_un_autre_ordre(
    fiche: Fiche, coherence_ok: FaitsCoherence, reglement: Reglement
) -> None:
    assert coherence_ok.certificat is not None
    fiche_composee = replace(fiche, prenom="Hélène Marie")
    faits = replace(
        coherence_ok, certificat=replace(coherence_ok.certificat, prenom="Marie Helene")
    )
    controle = _controle(fiche_composee, faits, reglement, "certificat_identite")
    assert controle.resultat is Resultat.CONFORME


def test_certificat_illisible(
    fiche: Fiche, coherence_ok: FaitsCoherence, reglement: Reglement
) -> None:
    faits = replace(coherence_ok, certificat=DonneesCertificat(page=1))
    controles = {c.code: c for c in verifier_coherence(fiche, faits, reglement)}
    for code in ("certificat_identite", "certificat_annee", "certificat_etablissement"):
        assert controles[code].resultat is Resultat.INDETERMINE
        assert controles[code].est_avertissement


@pytest.mark.parametrize(
    ("annee", "resultat"),
    [
        ("2026-2027", Resultat.CONFORME),
        ("2026/27", Resultat.CONFORME),
        ("2025-2026", Resultat.NON_CONFORME),
        ("illisible", Resultat.INDETERMINE),
    ],
)
def test_annee_certificat(
    fiche: Fiche,
    coherence_ok: FaitsCoherence,
    reglement: Reglement,
    annee: str,
    resultat: Resultat,
) -> None:
    assert coherence_ok.certificat is not None
    faits = replace(
        coherence_ok, certificat=replace(coherence_ok.certificat, annee_universitaire=annee)
    )
    controle = _controle(fiche, faits, reglement, "certificat_annee")
    assert controle.resultat is resultat
    if resultat is Resultat.NON_CONFORME:
        assert controle.effet is Consequence.A_COMPLETER


def test_certificat_autre_etablissement(
    fiche: Fiche, coherence_ok: FaitsCoherence, reglement: Reglement
) -> None:
    assert coherence_ok.certificat is not None
    faits = replace(
        coherence_ok,
        certificat=replace(coherence_ok.certificat, etablissement="Aix-Marseille Université"),
    )
    controle = _controle(fiche, faits, reglement, "certificat_etablissement")
    assert controle.resultat is Resultat.NON_CONFORME
    assert controle.effet is Consequence.A_COMPLETER


def test_lettre_incomplete_simple_avertissement(fiche: Fiche, reglement: Reglement) -> None:
    lettre = DonneesLettre(
        themes={
            "formation": ThemeLettre(True, "mon master", 5),
            "parcours": ThemeLettre(False),
        },
        page=5,
    )
    controle = _controle(fiche, FaitsCoherence(lettre=lettre), reglement, "lettre_themes")
    assert controle.resultat is Resultat.NON_CONFORME
    assert controle.consequence is Consequence.AVERTISSEMENT
    assert controle.effet is None
    assert "parcours, projet" in controle.message
    assert controle.preuves[0].extrait == "mon master"


def test_lettre_non_lue_indeterminee(fiche: Fiche, reglement: Reglement) -> None:
    lettre = DonneesLettre(themes={}, page=8)
    controle = _controle(fiche, FaitsCoherence(lettre=lettre), reglement, "lettre_themes")
    assert controle.resultat is Resultat.INDETERMINE
    assert controle.preuves[0].page == 8


def test_lettre_sans_theme_present_cite_la_page(fiche: Fiche, reglement: Reglement) -> None:
    lettre = DonneesLettre(themes={"formation": ThemeLettre(False)}, page=8)
    controle = _controle(fiche, FaitsCoherence(lettre=lettre), reglement, "lettre_themes")
    assert controle.resultat is Resultat.NON_CONFORME
    assert controle.preuves[0].page == 8


@pytest.mark.parametrize(
    ("annee", "resultat"),
    [
        ("2025-2026", Resultat.CONFORME),
        ("2024-2025", Resultat.NON_CONFORME),
        (None, Resultat.INDETERMINE),
    ],
)
def test_annee_releve(
    fiche: Fiche, reglement: Reglement, annee: str | None, resultat: Resultat
) -> None:
    faits = FaitsCoherence(releve=DonneesReleve(annee=annee, page=4))
    controle = _controle(fiche, faits, reglement, "releve_annee")
    assert controle.resultat is resultat
    assert controle.effet is None  # avertissement uniquement


@pytest.mark.parametrize(
    ("bourse", "resultat"),
    [
        (None, Resultat.CONFORME),
        ("Bourse CROUS sur critères sociaux", Resultat.CONFORME),
        ("Bourse Erasmus+", Resultat.NON_CONFORME),
    ],
)
def test_bourse_dans_attestation(
    fiche: Fiche, reglement: Reglement, bourse: str | None, resultat: Resultat
) -> None:
    faits = FaitsCoherence(attestation=DonneesAttestation(bourse_declaree=bourse, page=6))
    controle = _controle(fiche, faits, reglement, "attestation_bourse_declaree")
    assert controle.resultat is resultat
    if resultat is Resultat.NON_CONFORME:
        assert "la fiche n'en déclare aucune" in controle.message
        assert controle.effet is None
