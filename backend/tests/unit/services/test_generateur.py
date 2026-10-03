"""Les dossiers fictifs générés ont la structure attendue."""

import pymupdf
import pytest

from app.demo import pdf as demo

CANDIDAT = demo.Candidat("Dupont", "Hélène")


@pytest.mark.parametrize(
    ("scenario", "nb_pages"),
    [
        (demo.dossier_complet, 6),
        (demo.dossier_sans_lettre, 5),
        (demo.dossier_cv_trop_long, 7),
        (demo.dossier_certificat_scanne, 6),
        (demo.dossier_certificat_mauvais_nom, 6),
        (demo.dossier_injection, 5),
        (demo.dossier_avec_justificatifs, 9),
    ],
)
def test_nombre_de_pages(scenario, nb_pages: int) -> None:  # type: ignore[no-untyped-def]
    with pymupdf.open(stream=scenario(CANDIDAT), filetype="pdf") as document:
        assert document.page_count == nb_pages


def test_page_scannee_sans_couche_texte() -> None:
    with pymupdf.open(stream=demo.dossier_certificat_scanne(CANDIDAT), filetype="pdf") as doc:
        assert doc[0].get_text().strip() == ""
        assert doc[0].get_images()
        assert "CURRICULUM" in doc[1].get_text()


def test_generation_deterministe() -> None:
    assert demo.dossier_complet(CANDIDAT) == demo.dossier_complet(CANDIDAT)


def test_nom_fichier_conforme() -> None:
    assert CANDIDAT.nom_fichier == "BourseExcellence2026_DUPONT.HÉLÈNE.pdf"
