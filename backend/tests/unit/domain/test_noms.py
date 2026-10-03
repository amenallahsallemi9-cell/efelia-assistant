"""Normalisation des noms : accents, prénoms composés, ordre des prénoms."""

import pytest

from app.domain.noms import (
    compacter,
    identite_correspond,
    identite_presente_dans,
    jetons,
    nom_fichier_attendu,
    nom_fichier_conforme,
    normaliser,
    sans_accents,
)


@pytest.mark.parametrize(
    ("entree", "attendu"),
    [
        ("Hélène", "Helene"),
        ("Çağla Öztürk", "Cagla Ozturk"),
        ("Lætitia Œuvray", "Laetitia OEuvray"),
        ("NGUYỄN", "NGUYEN"),
    ],
)
def test_sans_accents(entree: str, attendu: str) -> None:
    assert sans_accents(entree) == attendu


@pytest.mark.parametrize(
    ("entree", "attendu"),
    [
        ("  Jean-Pierre  ", "jean pierre"),
        ("D'Artagnan", "d artagnan"),
        ("N’Diaye", "n diaye"),
        ("De La  Fontaine", "de la fontaine"),
        ("STRAßE", "strasse"),
    ],
)
def test_normaliser(entree: str, attendu: str) -> None:
    assert normaliser(entree) == attendu


def test_jetons_et_compacter() -> None:
    assert jetons("Marie-Claire Anne") == ("marie", "claire", "anne")
    assert compacter("De La Fontaine") == "delafontaine"
    assert compacter("N'Diaye") == compacter("NDIAYE")


@pytest.mark.parametrize(
    ("nom_doc", "prenom_doc"),
    [
        ("Dupont", "Hélène"),
        ("DUPONT", "HELENE"),
        ("dupont", "helene marie"),  # prénoms supplémentaires sur le document
        ("Hélène", "Dupont"),  # nom et prénom inversés
    ],
)
def test_identite_correspond(nom_doc: str, prenom_doc: str) -> None:
    assert identite_correspond("Dupont", "Hélène", nom_doc, prenom_doc)


@pytest.mark.parametrize(
    ("fiche", "doc"),
    [
        (("Martin", "Jean-Pierre"), ("MARTIN", "Jean Pierre")),
        (("Martin", "Jean-Pierre"), ("MARTIN", "Pierre Jean")),  # ordre des prénoms
        (("Martin", "Marie Claire Anne"), ("Martin", "Marie")),  # prénom usuel seul
        (("De La Fontaine", "Léa"), ("DELAFONTAINE", "Lea")),
        (("N'Diaye", "Awa"), ("NDIAYE", "AWA")),
        (("Le Goff", "Yann"), ("LE-GOFF", "Yann")),
    ],
)
def test_identite_tolerances(fiche: tuple[str, str], doc: tuple[str, str]) -> None:
    assert identite_correspond(*fiche, *doc)


@pytest.mark.parametrize(
    ("nom_doc", "prenom_doc"),
    [
        ("Durand", "Hélène"),
        ("Dupont", "Hugo"),
        ("Dupont", None),
        (None, "Hélène"),
        ("", ""),
    ],
)
def test_identite_differente(nom_doc: str | None, prenom_doc: str | None) -> None:
    assert not identite_correspond("Dupont", "Hélène Marie", nom_doc, prenom_doc)


def test_identite_prenoms_partiellement_communs_refusee() -> None:
    assert not identite_correspond("Dupont", "Hélène Marie", "Dupont", "Hélène Claire")


def test_identite_presente_dans_texte_libre() -> None:
    assert identite_presente_dans("Dupont", "Hélène Marie", "Mme DUPONT HELENE, née le…")
    assert not identite_presente_dans("Dupont", "Hélène", "Mme DURAND Hélène")
    assert not identite_presente_dans("Dupont", "", "Mme DUPONT")


def test_nom_fichier_attendu() -> None:
    attendu = nom_fichier_attendu("BourseExcellence2026", "De La Fontaine", "Jean-Pierre")
    assert attendu == "BourseExcellence2026_DE-LA-FONTAINE.JEAN-PIERRE.pdf"


@pytest.mark.parametrize(
    "fichier",
    [
        "BourseExcellence2026_DUPONT.HELENE.pdf",  # premier prénom seul
        "BourseExcellence2026_DUPONT.HÉLÈNE.pdf",
        "bourseexcellence2026_dupont.helene.PDF",
        "BourseExcellence2026_Dupont.Hélène",  # sans extension
        "BourseExcellence2026_DUPONT.HELENE-MARIE.pdf",  # tous les prénoms
        "BourseExcellence2026_DUPONT.HELENE MARIE.pdf",
    ],
)
def test_nom_fichier_conforme(fichier: str) -> None:
    assert nom_fichier_conforme(fichier, "BourseExcellence2026", "Dupont", "Hélène-Marie")


@pytest.mark.parametrize(
    "fichier",
    [
        "BourseExcellence2025_DUPONT.HELENE.pdf",  # mauvaise édition
        "BourseExcellence2026-DUPONT.HELENE.pdf",  # mauvais séparateur
        "BourseExcellence2026_DUPONT_HELENE.pdf",
        "BourseExcellence2026_HELENE.DUPONT.pdf",  # inversé
        "BourseExcellence2026_DURAND.HELENE.pdf",
        "BourseExcellence2026_DUPONT.MARIE.pdf",  # second prénom seul
        "dossier.pdf",
        "BourseExcellence2026_DUPONT.HELENE.docx",
    ],
)
def test_nom_fichier_non_conforme(fichier: str) -> None:
    assert not nom_fichier_conforme(fichier, "BourseExcellence2026", "Dupont", "Hélène-Marie")


def test_nom_fichier_nom_compose() -> None:
    for fichier in (
        "BourseExcellence2026_DE LA FONTAINE.LEA.pdf",
        "BourseExcellence2026_DE-LA-FONTAINE.LEA.pdf",
        "BourseExcellence2026_DELAFONTAINE.LEA.pdf",
    ):
        assert nom_fichier_conforme(fichier, "BourseExcellence2026", "De La Fontaine", "Léa")
