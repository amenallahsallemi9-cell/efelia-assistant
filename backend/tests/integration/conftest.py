"""Fixtures de l'API : planificateur synchrone (le pipeline s'exécute dans le test)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependances import get_planificateur
from app.core.config import Parametres
from app.core.reglement import get_reglement
from app.domain.regles import Reglement
from app.main import app
from app.workers.pipeline import PublieurNul, executer_pipeline


class PlanificateurSynchrone:
    """Exécute le pipeline immédiatement, dans la session de test."""

    def __init__(self, session: Session, parametres: Parametres, reglement: Reglement) -> None:
        self.session, self.parametres, self.reglement = session, parametres, reglement
        self.traitements: list[uuid.UUID] = []
        self.instructions: list[uuid.UUID] = []
        self.executer = True

    def planifier_traitement(self, dossier_id: uuid.UUID) -> None:
        self.traitements.append(dossier_id)
        if self.executer:
            executer_pipeline(
                self.session,
                dossier_id,
                self.parametres,
                PublieurNul(),
                ocr=lambda _: "",
                reglement=self.reglement,
            )

    def planifier_instruction(self, dossier_id: uuid.UUID) -> None:
        self.instructions.append(dossier_id)


@pytest.fixture
def planificateur(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> PlanificateurSynchrone:
    return PlanificateurSynchrone(session_test, parametres_test, reglement)


@pytest.fixture
def api(
    client: TestClient, planificateur: PlanificateurSynchrone, reglement: Reglement
) -> TestClient:
    # Les surcharges sont nettoyées par la fixture `client`.
    app.dependency_overrides[get_planificateur] = lambda: planificateur
    app.dependency_overrides[get_reglement] = lambda: reglement
    return client
