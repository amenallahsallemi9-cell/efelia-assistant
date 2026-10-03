"""Outils communs aux tests des services : pages ORM à partir d'un dossier généré."""

from pathlib import Path

from app.db.modeles import Page
from app.services.extraction import extraire_pages


def pages_depuis_pdf(contenu: bytes, dossier: Path) -> tuple[Path, list[Page]]:
    """Écrit le PDF et renvoie des objets `Page` (non persistés) issus de l'extraction."""
    chemin = dossier / "dossier.pdf"
    chemin.write_bytes(contenu)
    pages = [
        Page(
            numero=p.numero,
            texte=p.texte,
            methode=p.methode,
            type_piece=p.type_sensible,
            confiance_classification=p.confiance_sensible,
            sensible=p.type_sensible is not None,
        )
        for p in extraire_pages(chemin, lambda _: "")
    ]
    return chemin, pages
