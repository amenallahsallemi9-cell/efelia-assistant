"""`make seed` tient sa promesse : 5 dossiers, chacun avec le verdict annoncé."""

import shutil

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.db.modeles import Dossier
from app.demo.jeu_de_donnees import CAS, charger_demo
from app.domain.modeles import StatutPipeline, TypePiece, Verdict
from app.domain.regles import Reglement
from app.providers import construire_fournisseurs
from app.services.extraction import ocr_tesseract


@pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="Tesseract requis (certificat scanné)"
)
def test_jeu_de_demonstration(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    fournisseurs = construire_fournisseurs(parametres_test)
    resultats = charger_demo(session_test, parametres_test, reglement, fournisseurs, ocr_tesseract)

    assert len(resultats) == 5
    assert {r.cas.verdict_attendu for r in resultats} == set(Verdict)
    for r in resultats:
        assert r.statut_pipeline is StatutPipeline.INSTRUIT
        assert r.verdict is r.cas.verdict_attendu, r.cas.illustre

    par_nom = {r.cas.candidat.nom: session_test.get(Dossier, r.dossier_id) for r in resultats}
    leroy = par_nom["Leroy"]
    assert leroy is not None
    certificat = next(p for p in leroy.pieces if p.type is TypePiece.CERTIFICAT_SCOLARITE)
    assert certificat.donnees_extraites["nom"].upper().startswith("LEF")  # lu par OCR
    motifs = {m["code"] for m in leroy.decisions[-1].motifs if m["source"] == "regles"}
    assert {"certificat_identite", "cv_nombre_pages"} <= motifs

    bernard = par_nom["Bernard"]
    assert bernard is not None
    assert any(a["code"] == "injection_prompt" for a in bernard.decisions[-1].avertissements)

    # Idempotence : un second chargement remplace les dossiers de démonstration
    charger_demo(session_test, parametres_test, reglement, fournisseurs, ocr_tesseract)
    assert session_test.scalar(select(func.count()).select_from(Dossier)) == len(CAS)
