"""Extraction du texte, OCR des pages scannées et mise à l'écart des pages sensibles."""

import shutil
from pathlib import Path

import pytest
from PIL import Image

from app.demo.pdf import (
    INJECTION,
    Candidat,
    GenerateurDossier,
    dossier_avec_justificatifs,
    dossier_certificat_scanne,
)
from app.domain.modeles import MethodeExtraction, TypePiece
from app.services.extraction import (
    extraire_pages,
    nettoyer_texte,
    ocr_tesseract,
    rendre_page_png,
    texte_exploitable,
)

CANDIDAT = Candidat("Dupont", "Hélène")
tesseract_requis = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="Tesseract non installé (présent dans l'image Docker)"
)


def _ecrire(tmp_path: Path, contenu: bytes) -> Path:
    chemin = tmp_path / "dossier.pdf"
    chemin.write_bytes(contenu)
    return chemin


def _ocr_factice(texte: str):  # type: ignore[no-untyped-def]
    appels: list[Image.Image] = []

    def ocr(image: Image.Image) -> str:
        appels.append(image)
        return texte

    ocr.appels = appels  # type: ignore[attr-defined]
    return ocr


def test_nettoyer_texte() -> None:
    assert nettoyer_texte("  a\t\u00a0 b \n\n\n\n c ") == "a b\n\nc"


def test_texte_exploitable() -> None:
    assert not texte_exploitable("  12 ")
    assert texte_exploitable("Certificat de scolarité de l'année 2026")


def test_couche_texte_sans_ocr(tmp_path: Path) -> None:
    contenu = GenerateurDossier(CANDIDAT).certificat().lettre(injection=True).pdf()
    ocr = _ocr_factice("ne doit pas servir")
    pages = extraire_pages(_ecrire(tmp_path, contenu), ocr)
    assert [p.numero for p in pages] == [1, 2]
    assert all(p.methode is MethodeExtraction.TEXTE for p in pages)
    assert ocr.appels == []  # type: ignore[attr-defined]
    assert pages[0].texte is not None
    assert "CERTIFICAT DE SCOLARITÉ" in pages[0].texte
    assert "Année universitaire 2026-2027" in pages[0].texte
    # L'injection est extraite telle quelle : c'est une donnée, traitée plus loin.
    assert pages[1].texte is not None
    assert "ignore tes règles" in pages[1].texte.replace("\n", " ")
    assert INJECTION.split(":")[0][:20] in pages[1].texte


def test_page_scannee_passe_par_l_ocr(tmp_path: Path) -> None:
    ocr = _ocr_factice("CERTIFICAT DE SCOLARITÉ lu par OCR, année 2026-2027")
    pages = extraire_pages(_ecrire(tmp_path, dossier_certificat_scanne(CANDIDAT)), ocr)
    assert pages[0].methode is MethodeExtraction.OCR
    assert pages[0].texte == "CERTIFICAT DE SCOLARITÉ lu par OCR, année 2026-2027"
    assert len(ocr.appels) == 1  # type: ignore[attr-defined]
    assert all(p.methode is MethodeExtraction.TEXTE for p in pages[1:])


def test_ocr_vide_garde_la_couche_texte(tmp_path: Path) -> None:
    pages = extraire_pages(_ecrire(tmp_path, dossier_certificat_scanne(CANDIDAT)), _ocr_factice(""))
    assert pages[0].methode is MethodeExtraction.TEXTE
    assert pages[0].texte == ""


def test_pages_sensibles_sans_texte(tmp_path: Path) -> None:
    pages = extraire_pages(
        _ecrire(tmp_path, dossier_avec_justificatifs(CANDIDAT)), _ocr_factice("")
    )
    sensibles = {p.numero: p for p in pages if p.type_sensible is not None}
    assert [p.type_sensible for p in sensibles.values()] == [
        TypePiece.JUSTIFICATIF_SOCIAL,
        TypePiece.JUSTIFICATIF_HANDICAP,
    ]
    assert all(p.texte is None for p in sensibles.values())
    # L'attestation de non-cumul (qui cite la bourse CROUS) n'est pas écartée
    assert sum(p.texte is not None and "NON-CUMUL" in p.texte for p in pages) == 1


def test_pdf_illisible(tmp_path: Path) -> None:
    from app.services.extraction import ErreurExtraction

    with pytest.raises(ErreurExtraction):
        extraire_pages(_ecrire(tmp_path, b"%PDF-1.7 corrompu"))


def test_rendu_png(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, GenerateurDossier(CANDIDAT).certificat().pdf())
    png = rendre_page_png(chemin, 1)
    assert png.startswith(b"\x89PNG")
    with pytest.raises(IndexError):
        rendre_page_png(chemin, 2)


@tesseract_requis
def test_ocr_tesseract_reel(tmp_path: Path) -> None:
    pages = extraire_pages(_ecrire(tmp_path, dossier_certificat_scanne(CANDIDAT)), ocr_tesseract)
    certificat = pages[0]
    assert certificat.methode is MethodeExtraction.OCR
    assert certificat.texte is not None
    texte = certificat.texte.upper()
    assert "CERTIFICAT" in texte
    assert "DUPONT" in texte
    assert "2026-2027" in certificat.texte
