"""Format d'erreur homogène de l'API."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.erreurs import ErreurApi, installer_gestionnaires


class Corps(BaseModel):
    heures_ia: int


def _app() -> TestClient:
    app = FastAPI()
    installer_gestionnaires(app)

    @app.get("/metier")
    def metier() -> None:
        raise ErreurApi(404, "DOSSIER_INTROUVABLE", "Ce dossier n'existe pas.", {"id": "x"})

    @app.post("/valider")
    def valider(corps: Corps) -> Corps:
        return corps

    @app.get("/plantage")
    def plantage() -> None:
        raise RuntimeError("détail interne à ne pas exposer")

    return TestClient(app, raise_server_exceptions=False)


def test_erreur_metier() -> None:
    reponse = _app().get("/metier")
    assert reponse.status_code == 404
    assert reponse.json() == {
        "erreur": {
            "code": "DOSSIER_INTROUVABLE",
            "message": "Ce dossier n'existe pas.",
            "details": {"id": "x"},
        }
    }


def test_erreur_validation_en_francais() -> None:
    reponse = _app().post("/valider", json={"heures_ia": "beaucoup"})
    assert reponse.status_code == 422
    erreur = reponse.json()["erreur"]
    assert erreur["code"] == "VALIDATION"
    assert erreur["message"] == "Données invalides."
    assert erreur["details"][0]["champ"] == "body.heures_ia"


def test_route_inconnue() -> None:
    reponse = _app().get("/nexiste-pas")
    assert reponse.status_code == 404
    assert reponse.json()["erreur"]["code"] == "HTTP_404"


def test_erreur_inattendue_masquee() -> None:
    reponse = _app().get("/plantage")
    assert reponse.status_code == 500
    assert reponse.json()["erreur"]["code"] == "ERREUR_INTERNE"
    assert "détail interne" not in reponse.text
