"""Découpage en morceaux et préparation des corpus."""

from pathlib import Path

from app.db.modeles import Dossier, Page
from app.domain.modeles import MethodeExtraction, TypePiece
from app.services.indexation import (
    TAILLE_MAX,
    MorceauPrepare,
    decouper,
    preparer_dossier,
    preparer_reglement,
)
from app.services.recherche import requete_plein_texte

REGLEMENT = Path(__file__).resolve().parents[4] / "config" / "reglement_2026.md"


def test_paragraphes_courts_gardes_entiers() -> None:
    texte = "Premier paragraphe assez long pour compter.\n\nSecond paragraphe, lui aussi utile."
    assert decouper(texte) == [
        "Premier paragraphe assez long pour compter.",
        "Second paragraphe, lui aussi utile.",
    ]


def test_long_paragraphe_decoupe_avec_chevauchement() -> None:
    phrases = [f"Phrase numéro {i} qui parle du projet professionnel." for i in range(60)]
    morceaux = decouper(" ".join(phrases))
    assert len(morceaux) > 2
    assert all(len(m) <= TAILLE_MAX for m in morceaux)
    # La dernière phrase d'un morceau ouvre le suivant (continuité du contexte)
    derniere = morceaux[0].split(". ")[-1]
    assert morceaux[1].startswith(derniere.rstrip("."))
    assert "Phrase numéro 59" in morceaux[-1]


def test_fragments_trop_courts_ignores() -> None:
    assert decouper("Page 2\n\nUn paragraphe qui a du contenu exploitable.") == [
        "Un paragraphe qui a du contenu exploitable."
    ]
    assert decouper("CV") == ["CV"]  # mieux qu'aucun morceau
    assert decouper("   \n\n  ") == []


def test_phrase_geante_tronquee() -> None:
    assert all(len(m) <= TAILLE_MAX for m in decouper("x" * 5000))


def test_reglement_par_sections() -> None:
    morceaux = preparer_reglement(REGLEMENT.read_text(encoding="utf-8"))
    sections = {m.section for m in morceaux}
    assert {"Conditions d'éligibilité", "Date limite", "Pièces obligatoires"} <= sections
    date = next(m for m in morceaux if m.section == "Date limite")
    assert "18 octobre 2026" in date.texte
    assert date.texte_a_vectoriser.startswith("Date limite — ")
    assert all(m.page is None for m in morceaux)


def test_dossier_sans_pages_sensibles() -> None:
    dossier = Dossier(
        pages=[
            Page(
                numero=1,
                texte="Lettre : mon projet professionnel est clair et précis.",
                methode=MethodeExtraction.TEXTE,
                type_piece=TypePiece.LETTRE_MOTIVATION,
                sensible=False,
            ),
            Page(
                numero=2,
                texte=None,
                methode=MethodeExtraction.TEXTE,
                type_piece=TypePiece.JUSTIFICATIF_SOCIAL,
                sensible=True,
            ),
            Page(
                numero=3, texte="", methode=MethodeExtraction.OCR, type_piece=None, sensible=False
            ),
        ]
    )
    assert preparer_dossier(dossier) == [
        MorceauPrepare(
            "Lettre : mon projet professionnel est clair et précis.",
            section="Lettre de motivation",
            page=1,
            type_piece=TypePiece.LETTRE_MOTIVATION,
        )
    ]


def test_requete_plein_texte_sure() -> None:
    assert requete_plein_texte("Quelles pièces ?") == "quelles | pièces | pieces"
    assert requete_plein_texte("a & b | !c") is None
    assert requete_plein_texte("règles) & (DROP") == "règles | regles | drop"
