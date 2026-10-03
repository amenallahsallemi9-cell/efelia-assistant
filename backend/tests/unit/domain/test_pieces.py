"""Pièces obligatoires (→ A_COMPLETER si manquante), facultatives, CV, signature."""

from dataclasses import replace

import pytest

from app.domain.modeles import TypePiece, Verdict
from app.domain.regles import (
    Consequence,
    FaitsPieces,
    Reglement,
    Resultat,
    calculer_statut,
    verifier_pieces,
)


def _par_code(faits: FaitsPieces, reglement: Reglement) -> dict[str, Resultat]:
    return {c.code: c.resultat for c in verifier_pieces(faits, reglement)}


def test_dossier_complet(pieces_completes: FaitsPieces, reglement: Reglement) -> None:
    controles = verifier_pieces(pieces_completes, reglement)
    resultats = {c.code: c.resultat for c in controles}
    for piece in reglement.pieces_obligatoires:
        assert resultats[f"piece_{piece.type.value}"] is Resultat.CONFORME
    assert resultats["cv_nombre_pages"] is Resultat.CONFORME
    assert resultats["attestation_signature"] is Resultat.CONFORME
    assert calculer_statut(controles) is Verdict.RECEVABLE


def test_cinq_pieces_obligatoires(reglement: Reglement) -> None:
    assert {p.type for p in reglement.pieces_obligatoires} == {
        TypePiece.CERTIFICAT_SCOLARITE,
        TypePiece.CV,
        TypePiece.RELEVE_NOTES,
        TypePiece.LETTRE_MOTIVATION,
        TypePiece.ATTESTATION_NON_CUMUL,
    }


@pytest.mark.parametrize(
    "manquante",
    [
        p
        for p in TypePiece
        if p.value
        in {
            "certificat_scolarite",
            "cv",
            "releve_notes",
            "lettre_motivation",
            "attestation_non_cumul",
        }
    ],
)
def test_piece_manquante_a_completer(
    pieces_completes: FaitsPieces, reglement: Reglement, manquante: TypePiece
) -> None:
    pages = {t: p for t, p in pieces_completes.pages.items() if t is not manquante}
    controles = verifier_pieces(replace(pieces_completes, pages=pages), reglement)
    controle = next(c for c in controles if c.code == f"piece_{manquante.value}")
    assert controle.resultat is Resultat.NON_CONFORME
    assert controle.consequence is Consequence.A_COMPLETER
    assert "manquante" in controle.message
    assert calculer_statut(controles) is Verdict.A_COMPLETER


def test_dossier_vide(reglement: Reglement) -> None:
    controles = verifier_pieces(FaitsPieces(), reglement)
    assert calculer_statut(controles) is Verdict.A_COMPLETER
    assert sum(c.resultat is Resultat.NON_CONFORME for c in controles) == 5
    # Sans CV ni attestation, pas de contrôle de longueur ni de signature
    codes = {c.code for c in controles}
    assert "cv_nombre_pages" not in codes
    assert "attestation_signature" not in codes


def test_pieces_facultatives_sans_effet(
    pieces_completes: FaitsPieces, reglement: Reglement
) -> None:
    resultats = _par_code(pieces_completes, reglement)
    assert resultats["piece_lettre_recommandation"] is Resultat.NON_APPLICABLE
    assert resultats["piece_justificatif_social"] is Resultat.NON_APPLICABLE

    avec = replace(
        pieces_completes,
        pages={**pieces_completes.pages, TypePiece.LETTRE_RECOMMANDATION: (7,)},
    )
    controles = verifier_pieces(avec, reglement)
    reco = next(c for c in controles if c.code == "piece_lettre_recommandation")
    assert reco.resultat is Resultat.CONFORME
    assert reco.preuves[0].page == 7
    assert calculer_statut(controles) is Verdict.RECEVABLE


@pytest.mark.parametrize(
    ("nb_pages", "resultat", "statut"),
    [
        (1, Resultat.CONFORME, Verdict.RECEVABLE),
        (2, Resultat.CONFORME, Verdict.RECEVABLE),
        (3, Resultat.NON_CONFORME, Verdict.A_COMPLETER),
        (None, Resultat.INDETERMINE, Verdict.RECEVABLE),
    ],
)
def test_longueur_cv(
    pieces_completes: FaitsPieces,
    reglement: Reglement,
    nb_pages: int | None,
    resultat: Resultat,
    statut: Verdict,
) -> None:
    controles = verifier_pieces(replace(pieces_completes, cv_nb_pages=nb_pages), reglement)
    cv = next(c for c in controles if c.code == "cv_nombre_pages")
    assert cv.resultat is resultat
    assert cv.preuves[0].page == 2
    assert calculer_statut(controles) is statut


@pytest.mark.parametrize(
    ("signee", "resultat", "statut"),
    [
        (True, Resultat.CONFORME, Verdict.RECEVABLE),
        (False, Resultat.NON_CONFORME, Verdict.A_COMPLETER),
        (None, Resultat.INDETERMINE, Verdict.RECEVABLE),
    ],
)
def test_signature_attestation(
    pieces_completes: FaitsPieces,
    reglement: Reglement,
    signee: bool | None,
    resultat: Resultat,
    statut: Verdict,
) -> None:
    controles = verifier_pieces(replace(pieces_completes, attestation_signee=signee), reglement)
    signature = next(c for c in controles if c.code == "attestation_signature")
    assert signature.resultat is resultat
    assert signature.est_avertissement is (resultat is Resultat.INDETERMINE)
    assert calculer_statut(controles) is statut


def test_message_pages_multiples(pieces_completes: FaitsPieces, reglement: Reglement) -> None:
    cv = next(c for c in verifier_pieces(pieces_completes, reglement) if c.code == "piece_cv")
    assert cv.message == "Pièce présente (pages 2, 3)."
