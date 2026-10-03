"""Tâches du worker : relance, dossier supprimé, mise en file RQ (Redis réel)."""

import uuid

import pytest

from app.domain.modeles import StatutPipeline
from app.workers import pipeline
from app.workers.file import file_dossiers, mettre_en_file


@pytest.mark.parametrize(
    ("statut", "etapes"),
    [
        (StatutPipeline.INSTRUIT, ["instruction"]),
        (StatutPipeline.INDEXE, ["instruction"]),
        (
            StatutPipeline.ERREUR,
            ["extraction", "classification", "lecture", "indexation", "instruction"],
        ),
        (
            StatutPipeline.RECU,
            ["extraction", "classification", "lecture", "indexation", "instruction"],
        ),
    ],
)
def test_etapes_de_relance(statut: StatutPipeline, etapes: list[str]) -> None:
    assert [nom for _, nom, _ in pipeline.etapes_de_relance(statut)] == etapes


def test_taches_sur_dossier_supprime() -> None:
    inconnu = str(uuid.uuid4())
    assert pipeline.traiter_dossier(inconnu) == "SUPPRIME"
    assert pipeline.relancer_instruction(inconnu) == "SUPPRIME"


def test_mise_en_file() -> None:
    dossier_id = uuid.uuid4()
    file = file_dossiers()
    identifiant = mettre_en_file(dossier_id, fonction="app.workers.pipeline.relancer_instruction")
    tache = file.fetch_job(identifiant)
    try:
        assert tache is not None
        assert tache.func_name == "app.workers.pipeline.relancer_instruction"
        assert tache.args == (str(dossier_id),)
        assert tache.timeout == 15 * 60
    finally:
        if tache is not None:
            tache.delete()
