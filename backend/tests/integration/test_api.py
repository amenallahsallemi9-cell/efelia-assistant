"""API REST de bout en bout (httpx + base de test, mode démo, sans réseau)."""

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependances import get_planificateur
from app.core.config import Parametres
from app.core.reglement import get_reglement
from app.db.modeles import Dossier, Morceau, TraceAgent
from app.demo import pdf as demo
from app.domain.regles import Reglement
from app.main import app
from app.workers.pipeline import PublieurNul, canal_evenements, executer_pipeline

CANDIDAT = demo.Candidat("Dupont", "Hélène")
FICHE: dict[str, Any] = {
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


def deposer(
    api: TestClient,
    contenu: bytes | None = None,
    nom_fichier: str = CANDIDAT.nom_fichier,
    consentement: bool = True,
    **fiche: Any,
) -> Any:
    return api.post(
        "/api/dossiers",
        files={
            "fichier": (nom_fichier, contenu or demo.dossier_complet(CANDIDAT), "application/pdf")
        },
        data={"fiche": json.dumps({**FICHE, **fiche}), "consentement": str(consentement).lower()},
    )


# --------------------------------------------------------------------------- dépôt


def test_depot_puis_detail(api: TestClient, planificateur: PlanificateurSynchrone) -> None:
    reponse = deposer(api)
    assert reponse.status_code == 202, reponse.text
    corps = reponse.json()
    assert corps["statut_pipeline"] == "RECU"
    assert corps["nom_fichier_attendu"] == "BourseExcellence2026_DUPONT.HELENE.pdf"
    assert planificateur.traitements == [uuid.UUID(corps["id"])]

    detail = api.get(f"/api/dossiers/{corps['id']}").json()
    assert detail["statut_pipeline"] == "INSTRUIT"
    assert detail["fiche"]["prenom"] == "Hélène"
    assert len(detail["pages"]) == 6
    assert "texte" not in detail["pages"][0]  # le texte des pages n'est jamais exposé
    assert detail["pieces"][0]["type"] == "certificat_scolarite"
    decision = detail["decision"]
    assert decision["statut_regles"] == "RECEVABLE"
    assert decision["garde_fou_declenche"] is False
    assert decision["rapport"].startswith("# Rapport d'instruction")
    assert any(c["code"] == "eligibilite_heures_ia" for c in decision["controles"])
    assert detail["nb_decisions"] == 1


def test_depot_sans_consentement(api: TestClient, planificateur: PlanificateurSynchrone) -> None:
    reponse = deposer(api, consentement=False)
    assert reponse.status_code == 422
    assert reponse.json()["erreur"]["code"] == "CONSENTEMENT_REQUIS"
    assert planificateur.traitements == []


@pytest.mark.parametrize(
    ("fiche", "champ"),
    [({"heures_ia": -3}, "heures_ia"), ({"email": "x"}, "email"), ({"nom": ""}, "nom")],
)
def test_fiche_invalide(api: TestClient, fiche: dict[str, Any], champ: str) -> None:
    erreur = deposer(api, **fiche).json()["erreur"]
    assert erreur["code"] == "FICHE_INVALIDE"
    assert erreur["details"][0]["champ"] == champ


def test_fiche_json_mal_forme(api: TestClient) -> None:
    reponse = api.post(
        "/api/dossiers",
        files={"fichier": ("a.pdf", demo.dossier_complet(CANDIDAT), "application/pdf")},
        data={"fiche": "{pas du json", "consentement": "true"},
    )
    assert reponse.json()["erreur"]["code"] == "FICHE_INVALIDE"


def test_fichier_non_pdf(api: TestClient) -> None:
    reponse = deposer(api, contenu=b"PK\x03\x04 archive zip", nom_fichier="dossier.pdf")
    assert reponse.status_code == 415
    assert reponse.json()["erreur"] == {
        "code": "TYPE_NON_PDF",
        "message": "Le fichier n'est pas un PDF.",
        "details": None,
    }


def test_fichier_trop_volumineux(api: TestClient, parametres_test: Parametres) -> None:
    parametres_test.max_taille_mo = 1
    reponse = deposer(api, contenu=b"%PDF-" + b"0" * (1024 * 1024 + 10))
    assert reponse.status_code == 413
    assert reponse.json()["erreur"]["code"] == "FICHIER_TROP_VOLUMINEUX"


def test_fichier_absent(api: TestClient) -> None:
    reponse = api.post("/api/dossiers", data={"fiche": json.dumps(FICHE), "consentement": "true"})
    assert reponse.status_code == 422
    assert reponse.json()["erreur"]["code"] == "VALIDATION"


# --------------------------------------------------------------------------- liste et statistiques


@pytest.fixture
def plusieurs(api: TestClient) -> dict[str, str]:
    ids = {
        "complet": deposer(api).json()["id"],
        "sans_lettre": deposer(
            api,
            demo.dossier_sans_lettre(demo.Candidat("Martin", "Zoé")),
            nom="Martin",
            prenom="Zoé",
        ).json()["id"],
        "hors_delai": deposer(
            api, nom="Bernard", prenom="Léo", date_envoi="2026-10-20T08:00:00+02:00"
        ).json()["id"],
    }
    return ids


def test_liste_filtres_et_pagination(api: TestClient, plusieurs: dict[str, str]) -> None:
    tout = api.get("/api/dossiers").json()
    assert tout["total"] == 3
    assert {e["verdict"] for e in tout["elements"]} == {"RECEVABLE", "A_COMPLETER", "NON_RECEVABLE"}

    a_completer = api.get("/api/dossiers", params={"verdict": "A_COMPLETER"}).json()
    assert [e["id"] for e in a_completer["elements"]] == [plusieurs["sans_lettre"]]

    assert api.get("/api/dossiers", params={"recherche": "zo"}).json()["total"] == 1
    assert api.get("/api/dossiers", params={"recherche": "%"}).json()["total"] == 0
    assert api.get("/api/dossiers", params={"statut_pipeline": "RECU"}).json()["total"] == 0

    page = api.get("/api/dossiers", params={"taille": 2, "page": 2, "tri": "nom"}).json()
    assert page["total"] == 3
    assert [e["nom"] for e in page["elements"]] == ["Martin"]
    assert api.get("/api/dossiers", params={"taille": 500}).status_code == 422


def test_statistiques(api: TestClient, plusieurs: dict[str, str]) -> None:
    stats = api.get("/api/dossiers/statistiques").json()
    assert stats["total"] == 3
    assert stats["par_verdict"] == {"RECEVABLE": 1, "A_COMPLETER": 1, "NON_RECEVABLE": 1}
    assert stats["par_statut_pipeline"]["INSTRUIT"] == 3
    assert stats["pieces_manquantes"] == [
        {
            "type": "lettre_motivation",
            "libelle": "Lettre de motivation (formation, parcours, projet)",
            "nombre": 1,
        }
    ]
    assert stats["garde_fous_declenches"] == 0


# --------------------------------------------------------------------------- détail, images, trace


def test_dossier_inconnu(api: TestClient) -> None:
    reponse = api.get(f"/api/dossiers/{uuid.uuid4()}")
    assert reponse.status_code == 404
    assert reponse.json()["erreur"]["code"] == "DOSSIER_INTROUVABLE"
    assert api.get("/api/dossiers/pas-un-uuid").status_code == 422


def test_image_avec_surlignage(api: TestClient) -> None:
    dossier_id = deposer(api).json()["id"]
    url = f"/api/dossiers/{dossier_id}/pages/1/image"
    simple = api.get(url)
    assert simple.status_code == 200
    assert simple.headers["content-type"] == "image/png"
    assert simple.content.startswith(b"\x89PNG")
    assert simple.headers["x-zones-surlignees"] == "0"
    surligne = api.get(url, params={"surligner": "Année universitaire 2026-2027"})
    assert int(surligne.headers["x-zones-surlignees"]) >= 1
    assert surligne.content != simple.content
    absent = api.get(url, params={"surligner": "phrase qui n'existe pas dans la page"})
    assert absent.headers["x-zones-surlignees"] == "0"
    assert api.get(f"/api/dossiers/{dossier_id}/pages/99/image").json()["erreur"]["code"] == (
        "PAGE_INTROUVABLE"
    )


def test_page_sensible_masquee(api: TestClient) -> None:
    dossier_id = deposer(api, demo.dossier_avec_justificatifs(CANDIDAT)).json()["id"]
    masquee = api.get(
        f"/api/dossiers/{dossier_id}/pages/8/image", params={"surligner": "Revenu fiscal"}
    )
    assert masquee.status_code == 200
    assert masquee.headers["x-zones-surlignees"] == "0"


def test_trace(api: TestClient) -> None:
    dossier_id = deposer(api).json()["id"]
    trace = api.get(f"/api/dossiers/{dossier_id}/trace").json()
    outils = [t["outil"] for t in trace]
    assert outils[0] == "llm"
    assert "enregistrer_decision" in outils
    assert [t["ordre"] for t in trace] == list(range(1, len(trace) + 1))


# --------------------------------------------------------------------------- relance


def test_relancer_instruction(api: TestClient, planificateur: PlanificateurSynchrone) -> None:
    dossier_id = deposer(api).json()["id"]
    reponse = api.post(f"/api/dossiers/{dossier_id}/instruire")
    assert reponse.status_code == 202
    assert planificateur.instructions == [uuid.UUID(dossier_id)]


def test_relance_refusee_pendant_le_traitement(
    api: TestClient, planificateur: PlanificateurSynchrone
) -> None:
    planificateur.executer = False
    dossier_id = deposer(api).json()["id"]
    reponse = api.post(f"/api/dossiers/{dossier_id}/instruire")
    assert reponse.status_code == 409
    assert reponse.json()["erreur"]["code"] == "TRAITEMENT_EN_COURS"


# --------------------------------------------------------------------------- évènements (SSE)


def _evenements(texte: str) -> list[dict[str, Any]]:
    return [
        json.loads(ligne.removeprefix("data: "))
        for ligne in texte.splitlines()
        if ligne.startswith("data: ")
    ]


def test_sse_dossier_termine(api: TestClient) -> None:
    dossier_id = deposer(api).json()["id"]
    with api.stream("GET", f"/api/dossiers/{dossier_id}/evenements") as flux:
        assert flux.headers["content-type"].startswith("text/event-stream")
        texte = "".join(flux.iter_text())
    evenements = _evenements(texte)
    assert len(evenements) == 1
    assert evenements[0]["statut"] == "INSTRUIT"
    assert evenements[0]["etapes"][-1] == "INSTRUIT"


def test_sse_progression_en_direct(
    api: TestClient, planificateur: PlanificateurSynchrone, parametres_test: Parametres
) -> None:
    planificateur.executer = False
    dossier_id = deposer(api).json()["id"]
    redis = Redis.from_url(parametres_test.redis_url)
    canal = canal_evenements(uuid.UUID(dossier_id))

    def publier() -> None:
        # Attend l'abonnement du flux avant de publier
        for _ in range(100):
            if redis.pubsub_numsub(canal)[0][1]:
                break
            time.sleep(0.02)
        for statut in ("EXTRAIT", "CLASSE", "INSTRUIT"):
            redis.publish(canal, json.dumps({"statut": statut, "dossier_id": dossier_id}))

    fil = threading.Thread(target=publier)
    fil.start()
    with api.stream("GET", f"/api/dossiers/{dossier_id}/evenements") as flux:
        texte = "".join(flux.iter_text())
    fil.join()
    assert [e["statut"] for e in _evenements(texte)] == ["RECU", "EXTRAIT", "CLASSE", "INSTRUIT"]


def test_sse_dossier_inconnu(api: TestClient) -> None:
    assert api.get(f"/api/dossiers/{uuid.uuid4()}/evenements").status_code == 404


# --------------------------------------------------------------------------- effacement


def test_suppression_complete(
    api: TestClient, session_test: Session, parametres_test: Parametres
) -> None:
    dossier_id = deposer(api).json()["id"]
    dossier = session_test.get(Dossier, uuid.UUID(dossier_id))
    assert dossier is not None
    chemin = Path(dossier.chemin_fichier)
    assert chemin.exists()
    assert session_test.scalar(select(func.count()).where(Morceau.dossier_id == dossier.id))

    assert api.delete(f"/api/dossiers/{dossier_id}").status_code == 204
    assert not chemin.exists()
    session_test.expire_all()
    for table in (Morceau, TraceAgent):
        assert (
            session_test.scalar(
                select(func.count())
                .select_from(table)
                .where(table.dossier_id == uuid.UUID(dossier_id))
            )
            == 0
        )
    assert api.get(f"/api/dossiers/{dossier_id}").status_code == 404
    assert api.delete(f"/api/dossiers/{dossier_id}").status_code == 404


# --------------------------------------------------------------------------- éligibilité, règlement


@pytest.mark.parametrize(
    ("demande", "eligible", "delais"),
    [
        ({"heures_ia": 24}, True, True),
        ({"heures_ia": 23}, False, True),
        ({"alternance": True}, False, True),
        ({"autre_bourse": True, "autre_bourse_libelle": "CROUS échelon 3"}, True, True),
        ({"date_envoi": "2026-10-19T00:00:00+02:00"}, True, False),
    ],
)
def test_eligibilite(
    api: TestClient, demande: dict[str, Any], eligible: bool, delais: bool
) -> None:
    corps = {"inscrit_uca": True, "heures_ia": 30, "alternance": False, "autre_bourse": False}
    reponse = api.post(
        "/api/eligibilite",
        json={**corps, "date_envoi": "2026-10-10T12:00:00+02:00", **demande},
    ).json()
    assert reponse["eligible"] is eligible
    assert reponse["dans_les_delais"] is delais
    assert len(reponse["controles"]) == 5
    assert reponse["date_limite"].startswith("2026-10-19T00:00:00")


def test_eligibilite_invalide(api: TestClient) -> None:
    reponse = api.post("/api/eligibilite", json={"heures_ia": "beaucoup"})
    assert reponse.status_code == 422
    assert reponse.json()["erreur"]["code"] == "VALIDATION"


def test_resume_reglement(api: TestClient) -> None:
    resume = api.get("/api/reglement").json()
    assert resume["prefixe_nom_fichier"] == "BourseExcellence2026"
    assert resume["email_envoi"] == "EFELIA.bourses@univ-cotedazur.fr"
    assert len(resume["pieces_obligatoires"]) == 5
    assert resume["laureats_max"] == 15


def test_documentation_openapi(api: TestClient) -> None:
    schema = api.get("/api/openapi.json").json()
    chemins = set(schema["paths"])
    assert {
        "/api/dossiers",
        "/api/dossiers/{dossier_id}",
        "/api/dossiers/{dossier_id}/pages/{numero}/image",
        "/api/dossiers/{dossier_id}/instruire",
        "/api/dossiers/{dossier_id}/trace",
        "/api/dossiers/{dossier_id}/evenements",
        "/api/eligibilite",
        "/api/sante",
    } <= chemins
