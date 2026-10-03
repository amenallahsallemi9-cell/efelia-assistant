"""Aperçu PNG d'une page, avec surlignage d'un extrait (preuve) ou masquage (page sensible).

Le surlignage s'appuie sur la couche texte du PDF : il est impossible sur une page
scannée (OCR), qui s'affiche alors sans surlignage. Les justificatifs sensibles sont
toujours pixelisés : leur contenu n'a pas à être affiché par l'outil d'instruction.
"""

import io
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

DPI_APERCU = 110
DPI_MASQUE = 8
COULEUR_SURLIGNAGE = (1.0, 0.85, 0.2)


@dataclass(frozen=True)
class Apercu:
    """Image PNG et nombre de zones surlignées."""

    png: bytes
    zones: int


def localiser_zones(page: pymupdf.Page, extrait: str) -> list[pymupdf.Rect]:
    """Rectangles où figure l'extrait : texte entier, puis début, puis fin de l'extrait."""
    texte = " ".join(extrait.split())
    if not texte:
        return []
    mots = texte.split()
    candidats = [texte]
    if len(mots) > 6:
        candidats += [" ".join(mots[:6]), " ".join(mots[-6:])]
    for candidat in candidats:
        zones = page.search_for(candidat)
        if zones:
            return list(zones)
    # Dernier recours : les guillemets ou tirets typographiques diffèrent souvent.
    simplifie = re.sub(r"[«»“”\"’']", " ", " ".join(mots[:6])).split()
    if len(simplifie) >= 3:
        return list(page.search_for(" ".join(simplifie[:3])))
    return []


def _masquer(page: pymupdf.Page) -> bytes:
    reference = page.get_pixmap(dpi=DPI_APERCU)
    flou = page.get_pixmap(dpi=DPI_MASQUE)
    image = Image.open(io.BytesIO(flou.tobytes("png"))).convert("RGB")
    image = image.resize((reference.width, reference.height), Image.Resampling.NEAREST)
    dessin = ImageDraw.Draw(image)
    bandeau = (0, reference.height // 2 - 40, reference.width, reference.height // 2 + 40)
    dessin.rectangle(bandeau, fill=(30, 41, 59))
    police = ImageFont.load_default(size=22)
    message = "Justificatif sensible — aperçu masqué"
    largeur = dessin.textlength(message, font=police)
    dessin.text(
        ((reference.width - largeur) / 2, reference.height // 2 - 13),
        message,
        fill=(255, 255, 255),
        font=police,
    )
    sortie = io.BytesIO()
    image.save(sortie, format="PNG", optimize=True)
    return sortie.getvalue()


def rendre_apercu(
    chemin: Path, numero: int, *, surligner: str | None = None, masquer: bool = False
) -> Apercu:
    """Rend la page `numero` (à partir de 1). Lève IndexError si elle n'existe pas."""
    with pymupdf.open(chemin) as document:
        if not 1 <= numero <= document.page_count:
            raise IndexError(f"Page {numero} inexistante.")
        page = document[numero - 1]
        if masquer:
            return Apercu(_masquer(page), 0)
        zones = localiser_zones(page, surligner) if surligner else []
        for zone in zones:
            annotation = page.add_highlight_annot(zone)
            annotation.set_colors(stroke=COULEUR_SURLIGNAGE)
            annotation.update()
        return Apercu(bytes(page.get_pixmap(dpi=DPI_APERCU).tobytes("png")), len(zones))
