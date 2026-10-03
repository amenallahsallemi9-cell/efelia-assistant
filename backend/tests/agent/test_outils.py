"""Chaque outil de l'agent : résultat attendu et erreurs renvoyées au LLM."""

import json
import uuid
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.demo import pdf as demo
from app.domain.modeles import TypePiece
from app.domain.regles import Reglement
from app.providers import Fournisseurs
from app.providers.base import AppelOutil
from app.services.agent import outils as module_outils
from app.services.agent.contexte import ContexteAgent
from app.services.agent.outils import OUTILS, executer_outil, outils_pour_llm

from .conftest import FabriqueDossier, appel


@pytest.fixture
def contexte(
    preparer: FabriqueDossier,
    session_test: Session,
    reglement: Reglement,
    fournisseurs_demo: Fournisseurs,
) -> ContexteAgent:
    return ContexteAgent(
        session_test, preparer(demo.dossier_avec_justificatifs), reglement, fournisseurs_demo
    )


def _executer(contexte: ContexteAgent, nom: str, **args: Any) -> dict[str, Any]:
    return executer_outil(contexte, appel(nom, dossier_id=str(contexte.dossier.id), **args))


def test_neuf_outils_avec_schema() -> None:
    definitions = outils_pour_llm()
    assert [o.nom for o in definitions] == [
        "lire_fiche",
        "verifier_eligibilite",
        "verifier_format",
        "verifier_pieces",
        "lire_piece",
        "verifier_coherence",
        "rechercher_reglement",
        "rechercher_dans_dossier",
        "enregistrer_decision",
    ]
    for outil in definitions:
        assert outil.parametres["type"] == "object"
        assert "$ref" not in json.dumps(outil.parametres)
        assert outil.description


def test_lire_fiche_sans_email(contexte: ContexteAgent) -> None:
    fiche = _executer(contexte, "lire_fiche")
    assert fiche["nom"] == "Dupont"
    assert "email" not in fiche  # minimisation des données transmises au LLM
    assert fiche["nb_pages"] == 9
    assert fiche["pages"][7] == {
        "numero": 8,
        "type_piece": "justificatif_social",
        "methode": "texte",
        "sensible": True,
    }
    assert fiche["date_reception"].endswith("+02:00")
    assert fiche["alertes_injection"] == []


@pytest.mark.parametrize(
    "nom", ["verifier_eligibilite", "verifier_format", "verifier_pieces", "verifier_coherence"]
)
def test_outils_de_verification(contexte: ContexteAgent, nom: str) -> None:
    controles = _executer(contexte, nom)["controles"]
    assert controles
    assert {c["resultat"] for c in controles} <= {"CONFORME", "NON_APPLICABLE"}
    assert all({"code", "message", "preuves", "consequence"} <= set(c) for c in controles)


def test_lire_piece(contexte: ContexteAgent) -> None:
    lettre = _executer(contexte, "lire_piece", type_piece="lettre_motivation")
    assert lettre["present"] is True
    assert lettre["pages"] == [5]
    assert lettre["donnees"]["projet"]["present"] is True
    sensible = _executer(contexte, "lire_piece", type_piece="justificatif_social")
    assert "donnees" not in sensible
    assert "RGPD" in sensible["note"]
    assert _executer(contexte, "lire_piece", type_piece="autre") == {
        "present": False,
        "type_piece": "autre",
    }


def test_recherches(contexte: ContexteAgent) -> None:
    reglement = executer_outil(
        contexte, appel("rechercher_reglement", question="Quelle est la date limite ?")
    )
    assert any("18 octobre 2026" in r["texte"] for r in reglement["resultats"])
    dossier = _executer(contexte, "rechercher_dans_dossier", question="projet doctorat")
    assert dossier["resultats"][0]["page"] == 5
    assert dossier["resultats"][0]["piece"] == "lettre_motivation"


def test_enregistrer_decision_une_seule_fois(contexte: ContexteAgent) -> None:
    args = {
        "statut": "A_COMPLETER",
        "motifs": [{"message": "m", "page": 99}],
        "conseils": [{"categorie": "cv", "texte": "t", "page": 2}],
    }
    resultat = _executer(contexte, "enregistrer_decision", **args)
    assert resultat["statut_retenu"] == "RECEVABLE"
    assert resultat["ecart"] is True
    assert contexte.proposition is not None
    assert contexte.proposition.motifs[0]["page"] is None  # page inexistante neutralisée
    assert contexte.proposition.conseils[0]["page"] == 2
    second = _executer(contexte, "enregistrer_decision", **args)
    assert "déjà été enregistrée" in second["erreur"]


@pytest.mark.parametrize(
    ("appel_outil", "fragment"),
    [
        (AppelOutil("1", "supprimer_dossier", "{}"), "Outil inconnu"),
        (AppelOutil("2", "lire_fiche", "{pas du json"), "JSON mal formé"),
        (AppelOutil("3", "lire_fiche", "{}"), "dossier_id"),
        (AppelOutil("4", "lire_piece", '{"dossier_id": "x", "type_piece": "photo"}'), "type_piece"),
        (AppelOutil("5", "lire_fiche", '{"dossier_id": "x", "en_trop": 1}'), "en_trop"),
        (AppelOutil("6", "rechercher_reglement", '{"question": "?"}'), "question"),
    ],
)
def test_erreurs_renvoyees_au_llm(
    contexte: ContexteAgent, appel_outil: AppelOutil, fragment: str
) -> None:
    resultat = executer_outil(contexte, appel_outil)
    assert fragment in resultat["erreur"]


def test_acces_a_un_autre_dossier_refuse(contexte: ContexteAgent) -> None:
    resultat = executer_outil(contexte, appel("lire_fiche", dossier_id=str(uuid.uuid4())))
    assert resultat == {
        "erreur": "Accès refusé : seul le dossier en cours d'instruction est accessible."
    }


def test_exception_interne_masquee(
    contexte: ContexteAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    def panne(*_: Any) -> dict[str, Any]:
        raise RuntimeError("détail interne")

    monkeypatch.setitem(
        OUTILS,
        "lire_fiche",
        module_outils.DefinitionOutil("lire_fiche", "d", module_outils.ArgsDossier, panne),
    )
    assert _executer(contexte, "lire_fiche") == {"erreur": "Erreur interne de l'outil lire_fiche."}


def test_type_piece_enum_dans_le_schema() -> None:
    schema = OUTILS["lire_piece"].vers_outil().parametres
    assert set(schema["properties"]["type_piece"]["enum"]) == {t.value for t in TypePiece}
