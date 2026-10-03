"""Dossiers prêts à instruire (pipeline jusqu'à INDEXE, mode démo) et aides de scénario."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.db.modeles import Dossier
from app.demo import pdf as demo
from app.domain.regles import Reglement
from app.providers import Fournisseurs, construire_fournisseurs
from app.providers.base import AppelOutil, ReponseLLM
from app.providers.fake import FakeEmbeddings, FakeLLM, FakeReranker
from app.schemas import FicheDeclaree
from app.services.depot import creer_dossier
from app.workers.pipeline import ETAPES, PublieurNul, executer_pipeline

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

FabriqueDossier = Callable[..., Dossier]


@pytest.fixture
def preparer(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> FabriqueDossier:
    """Dépose un dossier et l'amène au statut INDEXE (sans l'instruire)."""

    def _preparer(
        scenario: Callable[[demo.Candidat], bytes] = demo.dossier_complet, **fiche: Any
    ) -> Dossier:
        dossier = creer_dossier(
            session_test,
            FicheDeclaree.model_validate({**FICHE, **fiche}),
            CANDIDAT.nom_fichier,
            scenario(CANDIDAT),
            parametres_test,
            reglement,
        )
        executer_pipeline(
            session_test,
            dossier.id,
            parametres_test,
            PublieurNul(),
            etapes=ETAPES[:4],
            ocr=lambda _: "",
            reglement=reglement,
        )
        session_test.refresh(dossier)
        return dossier

    return _preparer


def fournisseurs_scenario(*reponses: ReponseLLM | Exception) -> Fournisseurs:
    """Fournisseurs dont le LLM rejoue exactement les réponses données."""
    return Fournisseurs(FakeLLM(scenario=list(reponses)), FakeEmbeddings(), FakeReranker())


@pytest.fixture
def fournisseurs_demo(parametres_test: Parametres) -> Fournisseurs:
    return construire_fournisseurs(parametres_test)


def appel(nom: str, numero: int = 0, **arguments: Any) -> AppelOutil:
    return AppelOutil(f"{nom}_{numero}", nom, json.dumps(arguments))


def outils(*appels: AppelOutil, plan: str = "…") -> ReponseLLM:
    return ReponseLLM(appels_outils=appels, plan=plan, tokens_entree=100, tokens_sortie=20)


def decision(dossier: Dossier, statut: str, **extra: Any) -> AppelOutil:
    return appel(
        "enregistrer_decision",
        dossier_id=str(dossier.id),
        statut=statut,
        motifs=extra.get("motifs", []),
        conseils=extra.get("conseils", []),
    )
