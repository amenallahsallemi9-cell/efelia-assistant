"""Jeu de démonstration : 5 dossiers fictifs qui couvrent tous les cas d'instruction.

- Hélène Dupont → RECEVABLE : dossier complet, recommandation, justificatifs sensibles
  détectés mais jamais lus, bourse CROUS (cumulable) déclarée.
- Zoé Martin → A_COMPLETER : lettre de motivation manquante, nom de fichier non conforme.
- Inès Leroy → A_COMPLETER : certificat scanné (OCR) au nom d'une autre personne, CV de 3 pages.
- Léo Bernard → A_COMPLETER : injection de prompt dans la lettre, attestation manquante.
- Lina Moreau → NON_RECEVABLE : envoyé le 19 octobre à 00:12 (hors délai), 20 h d'IA seulement.

Les dossiers de démonstration sont reconnus à leur adresse `@demo.invalid` : un nouveau
chargement les remplace (idempotent).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.db.modeles import Dossier
from app.demo.pdf import Candidat, GenerateurDossier
from app.domain.modeles import StatutPipeline, Verdict
from app.domain.regles import Reglement
from app.providers import Fournisseurs
from app.schemas import FicheDeclaree
from app.services.depot import creer_dossier
from app.services.effacement import effacer_dossier
from app.services.extraction import FonctionOcr, ocr_tesseract
from app.workers.pipeline import PublieurNul, executer_pipeline

logger = logging.getLogger(__name__)

DOMAINE_DEMO = "demo.invalid"  # domaine réservé (RFC 2606) : aucune adresse réelle


@dataclass(frozen=True)
class CasDemo:
    """Un dossier de démonstration et le verdict attendu."""

    candidat: Candidat
    construire: Callable[[GenerateurDossier], GenerateurDossier]
    verdict_attendu: Verdict
    illustre: str
    nom_fichier: str | None = None
    fiche: dict[str, Any] = field(default_factory=dict)


CAS: tuple[CasDemo, ...] = (
    CasDemo(
        Candidat("Dupont", "Hélène"),
        lambda g: (
            g.certificat()
            .cv()
            .releve()
            .lettre()
            .attestation()
            .recommandation()
            .justificatif_social()
            .justificatif_handicap()
        ),
        Verdict.RECEVABLE,
        "Dossier complet ; justificatifs sensibles détectés mais jamais lus",
        fiche={
            "autre_bourse": True,
            "autre_bourse_libelle": "Bourse CROUS sur critères sociaux, échelon 5",
        },
    ),
    CasDemo(
        Candidat("Martin", "Zoé", formation="Master 2 Data Science"),
        lambda g: g.certificat().cv().releve().attestation(),
        Verdict.A_COMPLETER,
        "Lettre de motivation manquante ; nom de fichier non conforme (avertissement)",
        nom_fichier="dossier_candidature_zoe.pdf",
    ),
    CasDemo(
        Candidat("Leroy", "Inès", formation="Master 1 MIAGE, parcours IA"),
        lambda g: (
            g.certificat(nom="Lefèvre", prenom="Inès", scannee=True)
            .cv(nb_pages=3)
            .releve()
            .lettre()
            .attestation()
        ),
        Verdict.A_COMPLETER,
        "Certificat scanné (OCR) au nom d'une autre personne ; CV de 3 pages",
    ),
    CasDemo(
        Candidat("Bernard", "Léo"),
        lambda g: g.certificat().cv().releve().lettre(injection=True),
        Verdict.A_COMPLETER,
        "Injection de prompt dans la lettre (ignorée et signalée) ; attestation manquante",
    ),
    CasDemo(
        Candidat("Moreau", "Lina", formation="Licence 3 Informatique"),
        lambda g: g.certificat().cv().releve().lettre().attestation(),
        Verdict.NON_RECEVABLE,
        "Envoyé le 19 octobre à 00:12 (hors délai) ; 20 h d'IA seulement",
        fiche={"heures_ia": 20, "date_envoi": "2026-10-19T00:12:00+02:00"},
    ),
)


@dataclass(frozen=True)
class ResultatDemo:
    """Dossier créé et verdict obtenu."""

    cas: CasDemo
    dossier_id: str
    statut_pipeline: StatutPipeline
    verdict: Verdict | None


def supprimer_demo(session: Session, parametres: Parametres) -> int:
    """Efface les dossiers de démonstration existants."""
    existants = session.scalars(
        select(Dossier).where(Dossier.email.like(f"%@{DOMAINE_DEMO}"))
    ).all()
    for dossier in existants:
        effacer_dossier(session, dossier, parametres.stockage_dir)
    return len(existants)


def charger_demo(
    session: Session,
    parametres: Parametres,
    reglement: Reglement,
    fournisseurs: Fournisseurs,
    ocr: FonctionOcr = ocr_tesseract,
) -> list[ResultatDemo]:
    """(Re)crée les 5 dossiers et les traite entièrement (de RECU à INSTRUIT)."""
    supprimer_demo(session, parametres)
    resultats = []
    for cas in CAS:
        c = cas.candidat
        fiche = FicheDeclaree.model_validate(
            {
                "nom": c.nom,
                "prenom": c.prenom,
                "email": f"{c.prenom.lower()}.{c.nom.lower()}@{DOMAINE_DEMO}",
                "formation": c.formation,
                "inscrit_uca": True,
                "heures_ia": 48,
                "alternance": False,
                "autre_bourse": False,
                "date_envoi": "2026-10-12T14:30:00+02:00",
                **cas.fiche,
            }
        )
        contenu = cas.construire(GenerateurDossier(c)).pdf()
        dossier = creer_dossier(
            session, fiche, cas.nom_fichier or c.nom_fichier, contenu, parametres, reglement
        )
        statut = executer_pipeline(
            session,
            dossier.id,
            parametres,
            PublieurNul(),
            ocr=ocr,
            fournisseurs=fournisseurs,
            reglement=reglement,
        )
        session.refresh(dossier)
        decision = dossier.decisions[-1] if dossier.decisions else None
        resultats.append(
            ResultatDemo(cas, str(dossier.id), statut, decision.statut_regles if decision else None)
        )
    return resultats
