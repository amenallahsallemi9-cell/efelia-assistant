"""Sécurité HTTP : en-têtes, limitation de débit, et aucune donnée de document dans les logs."""

import json
import logging
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from redis import Redis

from app.core.config import Parametres, get_parametres
from app.core.logs import FormateurJson
from app.core.securite import autoriser
from app.demo import pdf as demo
from app.main import app

from .test_api import FICHE, deposer


def test_en_tetes_de_securite(client: TestClient) -> None:
    reponse = client.get("/api/sante")
    assert reponse.headers["x-content-type-options"] == "nosniff"
    assert reponse.headers["x-frame-options"] == "DENY"
    assert reponse.headers["referrer-policy"] == "no-referrer"
    assert (
        reponse.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )
    # La documentation interactive charge ses propres ressources : pas de CSP stricte
    assert "content-security-policy" not in client.get("/docs").headers


def test_autoriser_fenetre_fixe(parametres_test: Parametres) -> None:
    redis = Redis.from_url(parametres_test.redis_url)
    cle = f"test:{uuid.uuid4()}"
    assert [autoriser(redis, cle, 2, 60)[0] for _ in range(3)] == [True, True, False]
    assert 0 < autoriser(redis, cle, 2, 60)[1] <= 60


def test_autoriser_redis_indisponible() -> None:
    assert autoriser(
        Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.1), "x", 1, 60
    ) == (True, 0)


def test_limitation_des_depots(api: TestClient, parametres_test: Parametres) -> None:
    redis = Redis.from_url(parametres_test.redis_url)
    for cle in redis.scan_iter("limite:depot:testclient:*"):
        redis.delete(cle)
    limite = parametres_test.model_copy(update={"limite_depots_par_heure": 2})
    app.dependency_overrides[get_parametres] = lambda: limite
    codes = [deposer(api).status_code for _ in range(3)]
    assert codes == [202, 202, 429]
    reponse = deposer(api)
    assert reponse.json()["erreur"]["code"] == "TROP_DE_REQUETES"
    assert 0 < int(reponse.headers["retry-after"]) <= 3600


def test_aucune_donnee_de_document_dans_les_logs(
    api: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Parcours complet (dépôt → pipeline → agent → consultation → aperçu surligné → effacement) :
    les journaux ne contiennent que des identifiants, des statuts et des durées."""
    caplog.set_level(logging.DEBUG)
    candidat = demo.Candidat("Dupont", "Hélène")
    dossier_id = deposer(api, demo.dossier_avec_justificatifs(candidat)).json()["id"]
    api.get(f"/api/dossiers/{dossier_id}")
    api.get(f"/api/dossiers/{dossier_id}/trace")
    api.get(
        f"/api/dossiers/{dossier_id}/pages/1/image",
        params={"surligner": "Année universitaire 2026-2027"},
    )
    api.post(
        "/api/eligibilite",
        json={
            "inscrit_uca": True,
            "heures_ia": 30,
            "alternance": False,
            "autre_bourse": True,
            "autre_bourse_libelle": "Bourse Erasmus secrète",
        },
    )
    api.delete(f"/api/dossiers/{dossier_id}")

    formateur = FormateurJson()
    journal = "\n".join(formateur.format(r) for r in caplog.records)
    assert dossier_id in journal  # les identifiants, eux, sont bien journalisés
    interdits = [
        "Revenu fiscal",
        "12 345",
        "incapacité",
        "doctorat",
        "Année universitaire",
        "surligner",
        "Hélène",
        "DUPONT",
        FICHE["email"],
        "Erasmus",
        "ignore tes règles",
    ]
    fuites = [mot for mot in interdits if mot.lower() in journal.lower()]
    assert fuites == [], f"Données personnelles ou de document dans les logs : {fuites}"

    acces: list[dict[str, Any]] = [
        json.loads(formateur.format(r)) for r in caplog.records if r.name == "app.acces"
    ]
    assert any(e["chemin"].endswith("/pages/1/image") and e["code"] == 200 for e in acces)
    assert all("?" not in e["chemin"] for e in acces)
