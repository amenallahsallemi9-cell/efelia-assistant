"""`GET /api/sante` contre une vraie base PostgreSQL et un vrai Redis."""

from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis import Redis

from app.api.dependances import get_redis
from app.core.config import Parametres, get_parametres
from app.main import app


def test_sante_ok_en_mode_demo(client: TestClient) -> None:
    reponse = client.get("/api/sante")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == "ok"
    assert corps["mode_demo"] is True
    assert corps["base"]["etat"] == "ok"
    assert corps["redis"]["etat"] == "ok"
    assert corps["fournisseur_llm"]["etat"] == "ok"


def test_sante_degradee_si_redis_injoignable(client: TestClient) -> None:
    app.dependency_overrides[get_redis] = lambda: Redis.from_url(
        "redis://127.0.0.1:1/0", socket_connect_timeout=0.2
    )
    corps = client.get("/api/sante").json()
    assert corps["statut"] == "degrade"
    assert corps["redis"] == {"etat": "erreur", "detail": "Redis injoignable."}


def test_sante_degradee_si_cohere_sans_cle(client: TestClient) -> None:
    app.dependency_overrides[get_parametres] = lambda: Parametres(
        llm_provider="cohere", cohere_api_key=None
    )
    corps = client.get("/api/sante").json()
    assert corps["statut"] == "degrade"
    assert corps["mode_demo"] is False
    assert corps["fournisseur_llm"]["etat"] == "erreur"


def test_sante_cohere_configure_sans_appel_reseau(client: TestClient) -> None:
    app.dependency_overrides[get_parametres] = lambda: Parametres(
        llm_provider="auto", cohere_api_key=SecretStr("cle-de-test")
    )
    corps = client.get("/api/sante").json()
    assert corps["fournisseur_llm"] == {"etat": "ok", "detail": "Cohere configuré."}
