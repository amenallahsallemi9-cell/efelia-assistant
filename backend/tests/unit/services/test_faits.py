"""Conversion des données lues en faits du domaine."""

import pytest

from app.db.modeles import Piece
from app.domain.modeles import Confiance, TypePiece
from app.services.faits import construire_faits, deduire_signature


@pytest.mark.parametrize(
    ("donnees", "attendu"),
    [
        ({"signature_electronique": True, "marque_visuelle": False}, True),
        ({"marque_visuelle": True, "mention_signature": False}, True),
        ({"marque_visuelle": False, "mention_signature": False}, False),
        ({"marque_visuelle": False, "mention_signature": True}, None),
        ({"marque_visuelle": None, "mention_signature": True}, None),
        ({}, None),
    ],
)
def test_deduire_signature(donnees: dict[str, object], attendu: bool | None) -> None:
    assert deduire_signature(donnees) is attendu


def _piece(
    type_piece: TypePiece, pages: list[int], donnees: dict, confiance=Confiance.HAUTE
) -> Piece:  # type: ignore[no-untyped-def,type-arg]
    return Piece(type=type_piece, pages=pages, donnees_extraites=donnees, confiance=confiance)


def test_construire_faits_complets() -> None:
    pieces = [
        _piece(
            TypePiece.CERTIFICAT_SCOLARITE,
            [1],
            {
                "nom": "DUPONT",
                "prenom": "Hélène",
                "etablissement": "UCA",
                "annee_universitaire": "2026-2027",
                "extrait": "inscrite",
                "page": 1,
            },
        ),
        _piece(TypePiece.CV, [3, 2], {"competences": []}),
        _piece(TypePiece.RELEVE_NOTES, [4], {"annee": "2025-2026"}),
        _piece(
            TypePiece.LETTRE_MOTIVATION,
            [5],
            {
                "formation": {"present": True, "extrait": "M1", "page": 5},
                "parcours": {"present": False, "extrait": None, "page": None},
                "projet": "invalide",
            },
        ),
        _piece(
            TypePiece.ATTESTATION_NON_CUMUL,
            [6],
            {
                "marque_visuelle": True,
                "lieu_date": "Fait à Nice, le 1er octobre",
                "bourse_declaree": "",
                "extrait": None,
            },
        ),
    ]
    faits_pieces, faits_coherence = construire_faits(pieces)
    assert faits_pieces.pages[TypePiece.CV] == (2, 3)
    assert faits_pieces.cv_nb_pages == 2
    assert faits_pieces.attestation_signee is True
    assert faits_pieces.attestation_extrait == "Fait à Nice, le 1er octobre"
    assert faits_coherence.certificat is not None
    assert faits_coherence.certificat.nom == "DUPONT"
    assert faits_coherence.lettre is not None
    assert set(faits_coherence.lettre.themes) == {"formation", "parcours"}
    assert faits_coherence.lettre.themes["formation"].page == 5
    assert faits_coherence.releve is not None
    assert faits_coherence.releve.page == 4
    assert faits_coherence.attestation is not None
    assert faits_coherence.attestation.bourse_declaree is None


def test_pieces_absentes() -> None:
    faits_pieces, faits_coherence = construire_faits([])
    assert faits_pieces.cv_nb_pages is None
    assert faits_pieces.attestation_signee is None
    assert faits_coherence.certificat is None
    assert faits_coherence.lettre is None


def test_confiance_faible_devient_indeterminee() -> None:
    pieces = [
        _piece(
            TypePiece.CERTIFICAT_SCOLARITE,
            [1],
            {"nom": "MARTIN", "prenom": "Paul", "annee_universitaire": "2020-2021"},
            Confiance.FAIBLE,
        ),
        _piece(
            TypePiece.LETTRE_MOTIVATION, [2], {"formation": {"present": False}}, Confiance.FAIBLE
        ),
    ]
    _, faits = construire_faits(pieces)
    assert faits.certificat is not None
    assert faits.certificat.nom is None
    assert faits.certificat.annee_universitaire is None
    assert faits.certificat.page == 1
    assert faits.lettre is not None
    assert faits.lettre.themes == {}
