"""Pipeline complet jusqu'à la lecture (mode démo), puis verdict des règles par scénario.

Ces tests relient toute la chaîne : PDF → extraction → classification → lecture →
faits du domaine → règles. Aucun réseau, aucune clé API.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.db.modeles import Dossier
from app.demo import pdf as demo
from app.domain.instruction import instruire
from app.domain.modeles import Confiance, StatutPipeline, TypePiece, Verdict
from app.domain.regles import Reglement
from app.providers import construire_fournisseurs
from app.schemas import FicheDeclaree
from app.services.depot import creer_dossier
from app.services.faits import construire_faits
from app.workers.pipeline import PublieurNul, executer_pipeline

CANDIDAT = demo.Candidat("Dupont", "Hélène")
FICHE = {
    "nom": "Dupont",
    "prenom": "Hélène",
    "email": "helene.dupont@etu.univ-cotedazur.fr",
    "formation": "M1 Informatique",
    "inscrit_uca": True,
    "heures_ia": 48,
    "alternance": False,
    "autre_bourse": False,
    "date_envoi": "2026-10-10T10:00:00+02:00",
}


def _traiter(
    session: Session, parametres: Parametres, reglement: Reglement, contenu: bytes, **fiche: Any
) -> Dossier:
    dossier = creer_dossier(
        session,
        FicheDeclaree.model_validate({**FICHE, **fiche}),
        CANDIDAT.nom_fichier,
        contenu,
        parametres,
        reglement,
    )
    statut = executer_pipeline(
        session,
        dossier.id,
        parametres,
        PublieurNul(),
        ocr=lambda _: "",
        fournisseurs=construire_fournisseurs(parametres),
    )
    assert statut is StatutPipeline.LU, dossier.message_erreur
    session.refresh(dossier)
    return dossier


def _verdict(dossier: Dossier, reglement: Reglement) -> tuple[Verdict, set[str], set[str]]:
    fiche = FicheDeclaree.model_validate({**FICHE}).vers_domaine()
    faits_pieces, faits_coherence = construire_faits(dossier.pieces)
    instruction = instruire(
        fiche,
        dossier.nom_fichier,
        dossier.date_reception,
        faits_pieces,
        faits_coherence,
        reglement,
    )
    return (
        instruction.statut,
        {m.code for m in instruction.motifs},
        {a.code for a in instruction.avertissements},
    )


def test_dossier_complet_recevable(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    dossier = _traiter(session_test, parametres_test, reglement, demo.dossier_complet(CANDIDAT))
    pieces = {p.type: p for p in dossier.pieces}
    assert set(pieces) == {
        TypePiece.CERTIFICAT_SCOLARITE,
        TypePiece.CV,
        TypePiece.RELEVE_NOTES,
        TypePiece.LETTRE_MOTIVATION,
        TypePiece.ATTESTATION_NON_CUMUL,
    }
    assert pieces[TypePiece.CV].pages == [2, 3]
    assert all(p.confiance is Confiance.HAUTE for p in pieces.values())
    assert pieces[TypePiece.CERTIFICAT_SCOLARITE].donnees_extraites["annee_universitaire"] == (
        "2026-2027"
    )
    assert _verdict(dossier, reglement) == (Verdict.RECEVABLE, set(), set())


@pytest.mark.parametrize(
    ("scenario", "motifs", "avertissements"),
    [
        (demo.dossier_sans_lettre, {"piece_lettre_motivation"}, set()),
        (demo.dossier_cv_trop_long, {"cv_nombre_pages"}, set()),
        (demo.dossier_certificat_mauvais_nom, {"certificat_identite"}, set()),
        # Injection : lettre lue normalement ; l'attestation manque → A_COMPLETER
        (demo.dossier_injection, {"piece_attestation_non_cumul"}, set()),
    ],
)
def test_scenarios_a_completer(
    session_test: Session,
    parametres_test: Parametres,
    reglement: Reglement,
    scenario: Any,
    motifs: set[str],
    avertissements: set[str],
) -> None:
    dossier = _traiter(session_test, parametres_test, reglement, scenario(CANDIDAT))
    assert _verdict(dossier, reglement) == (Verdict.A_COMPLETER, motifs, avertissements)


def test_injection_signalee_dans_les_donnees(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    dossier = _traiter(session_test, parametres_test, reglement, demo.dossier_injection(CANDIDAT))
    lettre = next(p for p in dossier.pieces if p.type is TypePiece.LETTRE_MOTIVATION)
    alertes = lettre.donnees_extraites["alertes_injection"]
    assert len(alertes) == 1
    assert alertes[0]["page"] == 5  # certificat, CV (2 p.), relevé, puis la lettre


def test_justificatifs_detectes_jamais_lus(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    dossier = _traiter(
        session_test, parametres_test, reglement, demo.dossier_avec_justificatifs(CANDIDAT)
    )
    pieces = {p.type: p for p in dossier.pieces}
    assert pieces[TypePiece.JUSTIFICATIF_SOCIAL].donnees_extraites == {"document_detecte": True}
    assert pieces[TypePiece.JUSTIFICATIF_HANDICAP].pages == [9]
    assert TypePiece.LETTRE_RECOMMANDATION in pieces
    assert _verdict(dossier, reglement)[0] is Verdict.RECEVABLE


def test_hors_delai_non_recevable(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    dossier = _traiter(
        session_test,
        parametres_test,
        reglement,
        demo.dossier_complet(CANDIDAT),
        date_envoi="2026-10-19T00:00:00+02:00",
    )
    assert dossier.date_reception == datetime(2026, 10, 18, 22, 0, tzinfo=UTC)
    statut, motifs, _ = _verdict(dossier, reglement)
    assert (statut, motifs) == (Verdict.NON_RECEVABLE, {"format_delai"})


def test_page_jugee_sensible_par_le_llm_effacee(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    """Si le LLM reconnaît un justificatif que les mots-clés ont manqué, son texte est effacé."""
    import json

    from app.providers import Fournisseurs
    from app.providers.base import ReponseLLM
    from app.providers.fake import FakeEmbeddings, FakeLLM, FakeReranker

    heuristique = FakeLLM()

    def repondeur(messages: Any, outils: Any, format_json: Any) -> ReponseLLM:
        reponse = heuristique.discuter(messages, outils, format_json)
        if format_json.nom != "classement_pages":
            return reponse
        donnees = json.loads(reponse.texte or "{}")
        for page in donnees["pages"]:
            if page["numero"] == 4:
                page.update(type_piece="justificatif_social", confiance=0.9)
        return ReponseLLM(texte=json.dumps(donnees))

    dossier = creer_dossier(
        session_test,
        FicheDeclaree.model_validate(FICHE),
        CANDIDAT.nom_fichier,
        demo.dossier_complet(CANDIDAT),
        parametres_test,
        reglement,
    )
    fournisseurs = Fournisseurs(FakeLLM(repondeur=repondeur), FakeEmbeddings(), FakeReranker())
    executer_pipeline(
        session_test,
        dossier.id,
        parametres_test,
        PublieurNul(),
        ocr=lambda _: "",
        fournisseurs=fournisseurs,
    )
    session_test.refresh(dossier)
    page = next(p for p in dossier.pages if p.numero == 4)
    assert page.sensible is True
    assert page.texte is None
    assert page.type_piece is TypePiece.JUSTIFICATIF_SOCIAL


@pytest.mark.skipif(
    __import__("shutil").which("tesseract") is None, reason="Tesseract non installé"
)
def test_certificat_scanne_lu_par_ocr(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    from app.services.extraction import ocr_tesseract

    dossier = creer_dossier(
        session_test,
        FicheDeclaree.model_validate(FICHE),
        CANDIDAT.nom_fichier,
        demo.dossier_certificat_scanne(CANDIDAT),
        parametres_test,
        reglement,
    )
    executer_pipeline(
        session_test,
        dossier.id,
        parametres_test,
        PublieurNul(),
        ocr=ocr_tesseract,
        fournisseurs=construire_fournisseurs(parametres_test),
    )
    session_test.refresh(dossier)
    certificat = next(p for p in dossier.pieces if p.type is TypePiece.CERTIFICAT_SCOLARITE)
    assert certificat.pages == [1]
    assert certificat.donnees_extraites["annee_universitaire"] == "2026-2027"
    assert _verdict(dossier, reglement)[0] is Verdict.RECEVABLE
