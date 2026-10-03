"""Instruction complète et priorité des statuts (le calcul qui sert de garde-fou)."""

from dataclasses import replace
from datetime import datetime

from app.domain.coherence import DonneesCertificat, FaitsCoherence
from app.domain.instruction import instruire
from app.domain.modeles import TypePiece, Verdict
from app.domain.regles import (
    Categorie,
    Consequence,
    Controle,
    FaitsPieces,
    Fiche,
    Reglement,
    Resultat,
    calculer_statut,
)

from .conftest import PARIS

NOM_OK = "BourseExcellence2026_DUPONT.HELENE.pdf"


def _c(resultat: Resultat, consequence: Consequence) -> Controle:
    return Controle("x", Categorie.PIECES, "x", resultat, consequence, "x")


def test_statut_vide_recevable() -> None:
    assert calculer_statut([]) is Verdict.RECEVABLE


def test_priorite_non_recevable_sur_a_completer() -> None:
    controles = [
        _c(Resultat.NON_CONFORME, Consequence.A_COMPLETER),
        _c(Resultat.NON_CONFORME, Consequence.NON_RECEVABLE),
        _c(Resultat.CONFORME, Consequence.NON_RECEVABLE),
    ]
    assert calculer_statut(controles) is Verdict.NON_RECEVABLE


def test_avertissements_et_indetermines_sans_effet() -> None:
    controles = [
        _c(Resultat.NON_CONFORME, Consequence.AVERTISSEMENT),
        _c(Resultat.INDETERMINE, Consequence.NON_RECEVABLE),
        _c(Resultat.NON_APPLICABLE, Consequence.A_COMPLETER),
    ]
    assert calculer_statut(controles) is Verdict.RECEVABLE
    assert all(c.effet is None for c in controles)
    assert [c.est_avertissement for c in controles] == [True, True, False]


def test_dossier_complet_recevable(
    fiche: Fiche,
    date_ok: datetime,
    pieces_completes: FaitsPieces,
    coherence_ok: FaitsCoherence,
    reglement: Reglement,
) -> None:
    instruction = instruire(fiche, NOM_OK, date_ok, pieces_completes, coherence_ok, reglement)
    assert instruction.statut is Verdict.RECEVABLE
    assert instruction.motifs == ()
    assert instruction.avertissements == ()
    categories = {c.categorie for c in instruction.controles}
    assert categories == set(Categorie)


def test_piece_manquante_et_hors_delai(
    fiche: Fiche,
    pieces_completes: FaitsPieces,
    coherence_ok: FaitsCoherence,
    reglement: Reglement,
) -> None:
    sans_lettre = replace(
        pieces_completes,
        pages={
            t: p for t, p in pieces_completes.pages.items() if t is not TypePiece.LETTRE_MOTIVATION
        },
    )
    tard = datetime(2026, 10, 19, 0, 0, tzinfo=PARIS)
    instruction = instruire(fiche, NOM_OK, tard, sans_lettre, coherence_ok, reglement)
    assert instruction.statut is Verdict.NON_RECEVABLE
    assert {m.code for m in instruction.motifs} == {"format_delai", "piece_lettre_motivation"}


def test_avertissements_conserves_dossier_recevable(
    fiche: Fiche,
    date_ok: datetime,
    pieces_completes: FaitsPieces,
    coherence_ok: FaitsCoherence,
    reglement: Reglement,
) -> None:
    faits = replace(pieces_completes, attestation_signee=None)
    instruction = instruire(fiche, "dossier.pdf", date_ok, faits, coherence_ok, reglement)
    assert instruction.statut is Verdict.RECEVABLE
    assert {a.code for a in instruction.avertissements} == {
        "format_nom_fichier",
        "attestation_signature",
    }


def test_certificat_mauvais_nom_a_completer(
    fiche: Fiche,
    date_ok: datetime,
    pieces_completes: FaitsPieces,
    reglement: Reglement,
) -> None:
    coherence = FaitsCoherence(
        certificat=DonneesCertificat(
            nom="Martin",
            prenom="Paul",
            etablissement="Université Côte d'Azur",
            annee_universitaire="2026-2027",
            page=1,
        )
    )
    instruction = instruire(fiche, NOM_OK, date_ok, pieces_completes, coherence, reglement)
    assert instruction.statut is Verdict.A_COMPLETER
    assert [m.code for m in instruction.motifs] == ["certificat_identite"]
