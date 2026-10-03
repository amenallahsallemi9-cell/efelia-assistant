"""Conservation limitée : purge des dossiers expirés, fichiers orphelins, planification."""

import os
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from redis import Redis
from rq import Queue
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Parametres
from app.db.modeles import Dossier, Morceau
from app.demo import pdf as demo
from app.domain.regles import Reglement
from app.schemas import FicheDeclaree
from app.services.depot import creer_dossier
from app.services.purge import nettoyer_fichiers_orphelins, purger
from app.workers import purge as tache
from app.workers.pipeline import PublieurNul, executer_pipeline

FICHE = FicheDeclaree(
    nom="Dupont",
    prenom="Hélène",
    email="h@etu.fr",
    formation="M1",
    inscrit_uca=True,
    heures_ia=48,
    alternance=False,
    autre_bourse=False,
)
MAINTENANT = datetime(2026, 12, 1, tzinfo=UTC)


def _dossier(
    session: Session, parametres: Parametres, reglement: Reglement, age_jours: int
) -> Dossier:
    dossier = creer_dossier(
        session,
        FICHE,
        "x.pdf",
        demo.dossier_complet(demo.Candidat("Dupont", "Hélène")),
        parametres,
        reglement,
    )
    executer_pipeline(
        session, dossier.id, parametres, PublieurNul(), ocr=lambda _: "", reglement=reglement
    )
    dossier.created_at = MAINTENANT - timedelta(days=age_jours)
    session.commit()
    return dossier


def test_purge_des_dossiers_expires(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    ancien = _dossier(session_test, parametres_test, reglement, age_jours=200)
    recent = _dossier(session_test, parametres_test, reglement, age_jours=10)
    fichier_ancien, fichier_recent = Path(ancien.chemin_fichier), Path(recent.chemin_fichier)
    id_ancien = ancien.id

    bilan = purger(session_test, parametres_test.stockage_dir, 180, MAINTENANT)

    assert bilan.dossiers_effaces == 1
    assert not fichier_ancien.exists()
    assert fichier_recent.exists()
    assert session_test.get(Dossier, id_ancien) is None
    assert session_test.scalar(select(func.count()).where(Morceau.dossier_id == id_ancien)) == 0
    assert session_test.get(Dossier, recent.id) is not None


def test_fichiers_orphelins(
    session_test: Session, parametres_test: Parametres, reglement: Reglement
) -> None:
    connu = _dossier(session_test, parametres_test, reglement, age_jours=1)
    stockage = parametres_test.stockage_dir
    orphelin_ancien = stockage / "orphelin.pdf"
    orphelin_recent = stockage / "en_cours.part"
    autre = stockage / "notes.txt"
    for fichier in (orphelin_ancien, orphelin_recent, autre):
        fichier.write_bytes(b"x")
    il_y_a_2h = time.time() - 7200
    for fichier in (orphelin_ancien, autre, Path(connu.chemin_fichier)):
        os.utime(fichier, (il_y_a_2h, il_y_a_2h))

    assert nettoyer_fichiers_orphelins(session_test, stockage) == 1
    assert not orphelin_ancien.exists()
    assert orphelin_recent.exists()  # dépôt peut-être en cours
    assert autre.exists()  # pas un dossier
    assert Path(connu.chemin_fichier).exists()


def test_stockage_absent(session_test: Session, tmp_path: Path) -> None:
    assert nettoyer_fichiers_orphelins(session_test, tmp_path / "absent") == 0


@pytest.fixture
def file_test(parametres_test: Parametres) -> Iterator[Queue]:
    file = Queue(
        f"test-purge-{uuid.uuid4().hex[:6]}", connection=Redis.from_url(parametres_test.redis_url)
    )
    yield file
    for identifiant in file.scheduled_job_registry.get_job_ids():
        file.scheduled_job_registry.remove(identifiant, delete_job=True)
    file.empty()


def _prevues(file: Queue) -> list[str]:
    return [
        i for i in file.scheduled_job_registry.get_job_ids() if i.startswith(tache.PREFIXE_TACHE)
    ]


def test_purge_planifiee_une_seule_fois(file_test: Queue) -> None:
    assert tache.planifier_purge(file_test, delai=timedelta(hours=1)) is True
    assert tache.planifier_purge(file_test, delai=timedelta(hours=1)) is False
    assert len(_prevues(file_test)) == 1


def test_la_purge_se_replanifie_pendant_son_execution(
    file_test: Queue, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Régression : la tâche en cours ne doit pas empêcher de planifier la suivante."""
    from app.services.purge import BilanPurge
    from app.workers import file as module_file

    monkeypatch.setattr(tache, "executer_purge", lambda: BilanPurge(2, 1))
    monkeypatch.setattr(module_file, "file_dossiers", lambda: file_test)
    assert tache.tache_purge() == "2 dossier(s), 1 orphelin(s)"
    assert len(_prevues(file_test)) == 1
