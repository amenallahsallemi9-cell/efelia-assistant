"""Étape 2 : extraction du texte page par page (PyMuPDF), avec OCR Tesseract si nécessaire.

Les pages détectées comme justificatifs sensibles (sociaux, handicap) sont marquées
`sensible` et leur texte est **immédiatement écarté** : il n'est ni stocké, ni envoyé
au LLM, ni indexé.
"""

import io
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.modeles import Dossier, Page
from app.domain.modeles import MethodeExtraction, TypePiece
from app.domain.sensibles import detecter_page_sensible

logger = logging.getLogger(__name__)

#: En dessous de ce nombre de caractères alphanumériques, la page est considérée scannée.
SEUIL_TEXTE_EXPLOITABLE = 25
DPI_OCR = 250
LANGUE_OCR = "fra"

FonctionOcr = Callable[[Image.Image], str]


class ErreurExtraction(Exception):
    """Échec de lecture du PDF."""


@dataclass(frozen=True)
class PageExtraite:
    """Texte d'une page et méthode d'obtention. `texte` est None pour une page sensible."""

    numero: int
    texte: str | None
    methode: MethodeExtraction
    type_sensible: TypePiece | None = None
    confiance_sensible: float | None = None


def ocr_tesseract(image: Image.Image) -> str:
    """OCR français avec Tesseract."""
    import pytesseract

    return str(pytesseract.image_to_string(image, lang=LANGUE_OCR))


def texte_exploitable(texte: str) -> bool:
    """Vrai si la couche texte contient assez de caractères pour être utilisée."""
    return len(re.findall(r"\w", texte)) >= SEUIL_TEXTE_EXPLOITABLE


def nettoyer_texte(texte: str) -> str:
    """Normalise les espaces sans altérer le contenu."""
    lignes = (re.sub(r"[ \t ]+", " ", ligne).strip() for ligne in texte.splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lignes)).strip()


def _image_page(page: pymupdf.Page, dpi: int) -> Image.Image:
    pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    return Image.open(io.BytesIO(pixmap.tobytes("png")))


def extraire_pages(chemin: Path, ocr: FonctionOcr = ocr_tesseract) -> list[PageExtraite]:
    """Extrait chaque page : couche texte si exploitable, sinon OCR ; écarte les pages sensibles."""
    try:
        document = pymupdf.open(chemin)
    except Exception as exc:
        raise ErreurExtraction("Impossible d'ouvrir le PDF.") from exc

    pages: list[PageExtraite] = []
    with document:
        for index, page in enumerate(document):
            texte = nettoyer_texte(page.get_text("text"))
            methode = MethodeExtraction.TEXTE
            if not texte_exploitable(texte):
                texte_ocr = nettoyer_texte(ocr(_image_page(page, DPI_OCR)))
                if len(texte_ocr) > len(texte):
                    texte, methode = texte_ocr, MethodeExtraction.OCR

            detection = detecter_page_sensible(texte)
            if detection is not None:
                pages.append(
                    PageExtraite(
                        numero=index + 1,
                        texte=None,
                        methode=methode,
                        type_sensible=detection.type_piece,
                        confiance_sensible=detection.confiance,
                    )
                )
            else:
                pages.append(PageExtraite(numero=index + 1, texte=texte, methode=methode))
    return pages


def enregistrer_pages(session: Session, dossier: Dossier, pages: list[PageExtraite]) -> None:
    """Remplace les pages du dossier par celles extraites (idempotent en cas de relance)."""
    session.execute(delete(Page).where(Page.dossier_id == dossier.id))
    for extraite in pages:
        session.add(
            Page(
                dossier_id=dossier.id,
                numero=extraite.numero,
                texte=extraite.texte,
                methode=extraite.methode,
                type_piece=extraite.type_sensible,
                confiance_classification=extraite.confiance_sensible,
                sensible=extraite.type_sensible is not None,
            )
        )
    dossier.nb_pages = len(pages)
    session.flush()


def executer_extraction(
    session: Session, dossier: Dossier, ocr: FonctionOcr = ocr_tesseract
) -> list[PageExtraite]:
    """Étape complète d'extraction pour un dossier."""
    pages = extraire_pages(Path(dossier.chemin_fichier), ocr)
    enregistrer_pages(session, dossier, pages)
    logger.info(
        "Extraction terminée",
        extra={
            "dossier_id": str(dossier.id),
            "etape": "EXTRAIT",
            "methode": f"{sum(p.methode is MethodeExtraction.OCR for p in pages)} page(s) OCR",
        },
    )
    return pages


def rendre_page_png(chemin: Path, numero: int, dpi: int = 110) -> bytes:
    """Aperçu PNG d'une page (numérotation à partir de 1)."""
    with pymupdf.open(chemin) as document:
        if not 1 <= numero <= document.page_count:
            raise IndexError(f"Page {numero} inexistante.")
        return bytes(document[numero - 1].get_pixmap(dpi=dpi).tobytes("png"))
