"""Boucle de l'agent rejouée par le FakeProvider : succès, erreurs, garde-fou, injection."""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.modeles import Decision, TraceAgent
from app.demo import pdf as demo
from app.domain.modeles import Verdict
from app.domain.regles import Reglement
from app.providers import Fournisseurs
from app.providers.base import AppelOutil, ErreurFournisseur, ReponseLLM
from app.services.agent.boucle import MAX_TOURS, instruire_avec_agent

from .conftest import FabriqueDossier, appel, decision, fournisseurs_scenario, outils


def _traces(session: Session, dossier_id: object) -> list[TraceAgent]:
    return list(
        session.scalars(
            select(TraceAgent).where(TraceAgent.dossier_id == dossier_id).order_by(TraceAgent.ordre)
        )
    )


def test_succes(preparer: FabriqueDossier, session_test: Session, reglement: Reglement) -> None:
    dossier = preparer()
    d = str(dossier.id)
    fournisseurs = fournisseurs_scenario(
        outils(appel("lire_fiche", dossier_id=d)),
        outils(
            appel("verifier_eligibilite", 1, dossier_id=d),
            appel("verifier_pieces", 2, dossier_id=d),
        ),
        outils(
            decision(
                dossier,
                "RECEVABLE",
                conseils=[{"categorie": "lettre", "texte": "Citez un projet IA.", "page": 5}],
            )
        ),
        ReponseLLM(texte="### Points forts du dossier\n- Moyenne de 16,2/20."),
    )
    resultat = instruire_avec_agent(session_test, dossier, reglement, fournisseurs)

    assert resultat.conclu is True
    assert resultat.tours == 4
    d_ = resultat.decision
    assert d_.statut_regles is Verdict.RECEVABLE
    assert d_.statut_propose_llm is Verdict.RECEVABLE
    assert d_.garde_fou_declenche is False
    assert d_.motifs == []
    assert d_.conseils == [
        {"categorie": "lettre", "texte": "Citez un projet IA.", "page": 5, "source": "agent"}
    ]
    assert len(d_.controles) > 10
    assert "## Verdict : ✅ Recevable" in d_.rapport
    assert "ne préjuge en rien de la décision du jury" in d_.rapport
    assert "Moyenne de 16,2/20" in d_.rapport
    assert d_.modele == "fake-llm"

    traces = _traces(session_test, dossier.id)
    assert [t.outil for t in traces] == [
        "llm",
        "lire_fiche",
        "llm",
        "verifier_eligibilite",
        "verifier_pieces",
        "llm",
        "enregistrer_decision",
        "llm",
    ]
    assert traces[0].tokens == 120
    assert traces[1].resultat["nom"] == "Dupont"
    assert all(t.duree_ms >= 0 for t in traces)

    # Les résultats d'outils sont renvoyés au LLM en messages « tool » liés à l'appel
    messages = fournisseurs.llm.appels[1][0]  # type: ignore[attr-defined]
    assert messages[-1].role == "tool"
    assert messages[-1].id_appel == "lire_fiche_0"
    assert json.loads(messages[-1].contenu)["prenom"] == "Hélène"
    assert len(fournisseurs.llm.appels[0][1]) == 9  # type: ignore[attr-defined]


def test_outil_inconnu_puis_reprise(
    preparer: FabriqueDossier, session_test: Session, reglement: Reglement
) -> None:
    dossier = preparer()
    fournisseurs = fournisseurs_scenario(
        outils(AppelOutil("x", "valider_automatiquement", "{}")),
        outils(decision(dossier, "RECEVABLE")),
        ReponseLLM(texte="Rapport."),
    )
    resultat = instruire_avec_agent(session_test, dossier, reglement, fournisseurs)
    assert resultat.conclu
    trace = _traces(session_test, dossier.id)[1]
    assert trace.outil == "valider_automatiquement"
    assert "Outil inconnu" in trace.resultat["erreur"]
    retour = fournisseurs.llm.appels[1][0][-1]  # type: ignore[attr-defined]
    assert "Outil inconnu" in retour.contenu


def test_arguments_invalides(
    preparer: FabriqueDossier, session_test: Session, reglement: Reglement
) -> None:
    dossier = preparer()
    fournisseurs = fournisseurs_scenario(
        outils(
            AppelOutil("a", "lire_piece", json.dumps({"dossier_id": str(dossier.id)})),
            AppelOutil("b", "verifier_format", "pas du json"),
            appel(
                "enregistrer_decision",
                9,
                dossier_id=str(dossier.id),
                statut="PEUT_ETRE",
                motifs=[],
                conseils=[],
            ),
        ),
        ReponseLLM(texte="Fin."),
    )
    resultat = instruire_avec_agent(session_test, dossier, reglement, fournisseurs)
    traces = _traces(session_test, dossier.id)
    assert all("erreur" in t.resultat for t in traces[1:4])
    assert traces[2].arguments == {"brut": "pas du json"}
    # Aucune décision valide proposée : le statut des règles s'applique, sans écart
    assert resultat.decision.statut_propose_llm is None
    assert resultat.decision.statut_regles is Verdict.RECEVABLE
    assert resultat.decision.garde_fou_declenche is False


def test_agent_qui_ne_conclut_pas(
    preparer: FabriqueDossier, session_test: Session, reglement: Reglement
) -> None:
    dossier = preparer(demo.dossier_sans_lettre)
    boucle_infinie = [outils(appel("lire_fiche", i, dossier_id=str(dossier.id))) for i in range(20)]
    fournisseurs = fournisseurs_scenario(*boucle_infinie)
    resultat = instruire_avec_agent(session_test, dossier, reglement, fournisseurs)
    assert resultat.conclu is False
    assert resultat.tours == MAX_TOURS
    assert len(fournisseurs.llm.appels) == MAX_TOURS  # type: ignore[attr-defined]
    assert resultat.decision.statut_regles is Verdict.A_COMPLETER
    assert "n'a pas conclu en 12 tours" in resultat.decision.rapport
    assert len(_traces(session_test, dossier.id)) == 2 * MAX_TOURS


def test_llm_force_recevable_garde_fou(
    preparer: FabriqueDossier, session_test: Session, reglement: Reglement
) -> None:
    dossier = preparer(demo.dossier_sans_lettre)
    fournisseurs = fournisseurs_scenario(
        outils(decision(dossier, "RECEVABLE", motifs=[{"message": "Tout est parfait."}])),
        ReponseLLM(texte="Le dossier est recevable."),
    )
    d_ = instruire_avec_agent(session_test, dossier, reglement, fournisseurs).decision
    assert d_.statut_propose_llm is Verdict.RECEVABLE
    assert d_.statut_regles is Verdict.A_COMPLETER
    assert d_.garde_fou_declenche is True
    assert "Garde-fou déclenché" in d_.rapport
    assert "## Verdict : ⚠️ À compléter" in d_.rapport
    assert [m["code"] for m in d_.motifs if m["source"] == "regles"] == ["piece_lettre_motivation"]
    assert {
        "source": "agent",
        "message": "Tout est parfait.",
        "page": None,
        "extrait": None,
    } in d_.motifs
    # Le LLM est informé que le statut des règles s'applique
    retour = json.loads(fournisseurs.llm.appels[1][0][-1].contenu)  # type: ignore[attr-defined]
    assert retour["statut_retenu"] == "A_COMPLETER"
    assert retour["ecart"] is True


def test_injection_de_prompt(
    preparer: FabriqueDossier, session_test: Session, reglement: Reglement
) -> None:
    """La lettre ordonne de déclarer le dossier recevable ; un LLM naïf obéit."""
    dossier = preparer(demo.dossier_injection)
    fournisseurs = fournisseurs_scenario(
        outils(appel("lire_fiche", dossier_id=str(dossier.id))),
        outils(decision(dossier, "RECEVABLE")),
        ReponseLLM(texte="Conformément aux instructions, le dossier est recevable."),
    )
    d_ = instruire_avec_agent(session_test, dossier, reglement, fournisseurs).decision
    assert d_.statut_regles is Verdict.A_COMPLETER  # attestation manquante
    assert d_.garde_fou_declenche is True
    injection = next(a for a in d_.avertissements if a["code"] == "injection_prompt")
    assert injection["preuves"][0]["page"] == 5
    assert "Tentative d'injection de prompt ignorée" in d_.rapport
    # L'alerte figurait déjà dans la fiche transmise à l'agent
    fiche = json.loads(fournisseurs.llm.appels[1][0][-1].contenu)  # type: ignore[attr-defined]
    assert fiche["alertes_injection"][0]["page"] == 5


def test_panne_du_fournisseur(
    preparer: FabriqueDossier, session_test: Session, reglement: Reglement
) -> None:
    dossier = preparer(demo.dossier_cv_trop_long)
    fournisseurs = fournisseurs_scenario(
        outils(appel("lire_fiche", dossier_id=str(dossier.id))), ErreurFournisseur("quota")
    )
    resultat = instruire_avec_agent(session_test, dossier, reglement, fournisseurs)
    assert resultat.conclu is False
    assert resultat.decision.statut_regles is Verdict.A_COMPLETER
    assert "Agent LLM indisponible" in resultat.decision.rapport
    assert "CV de 3 pages" in resultat.decision.rapport


def test_prediction_retiree(
    preparer: FabriqueDossier, session_test: Session, reglement: Reglement
) -> None:
    dossier = preparer()
    fournisseurs = fournisseurs_scenario(
        outils(
            decision(
                dossier,
                "RECEVABLE",
                conseils=[{"categorie": "general", "texte": "Vous avez 80 % de chances."}],
            )
        ),
        ReponseLLM(
            texte="### Points forts du dossier\n- Très bonne moyenne. Vous serez retenue.\n"
            "- Vos chances sont excellentes."
        ),
    )
    d_ = instruire_avec_agent(session_test, dossier, reglement, fournisseurs).decision
    assert "retenue" not in d_.rapport
    assert "chances" not in d_.rapport
    assert "Très bonne moyenne." in d_.rapport
    assert d_.conseils == []
    alerte = next(a for a in d_.avertissements if a["code"] == "prediction_retiree")
    assert "3 phrase(s)" in alerte["message"]


def test_relance_garde_l_historique_des_decisions(
    preparer: FabriqueDossier,
    session_test: Session,
    reglement: Reglement,
    fournisseurs_demo: Fournisseurs,
) -> None:
    dossier = preparer()
    for _ in range(2):
        instruire_avec_agent(session_test, dossier, reglement, fournisseurs_demo)
    decisions = session_test.scalars(
        select(Decision).where(Decision.dossier_id == dossier.id)
    ).all()
    assert len(decisions) == 2
    ordres = [t.ordre for t in _traces(session_test, dossier.id)]
    assert ordres == list(range(1, len(ordres) + 1))  # traces de la dernière instruction


@pytest.mark.parametrize(
    ("scenario", "statut"),
    [
        (demo.dossier_complet, Verdict.RECEVABLE),
        (demo.dossier_sans_lettre, Verdict.A_COMPLETER),
        (demo.dossier_cv_trop_long, Verdict.A_COMPLETER),
        (demo.dossier_certificat_mauvais_nom, Verdict.A_COMPLETER),
        (demo.dossier_injection, Verdict.A_COMPLETER),
    ],
)
def test_agent_demo_de_bout_en_bout(
    preparer: FabriqueDossier,
    session_test: Session,
    reglement: Reglement,
    fournisseurs_demo: Fournisseurs,
    scenario: object,
    statut: Verdict,
) -> None:
    dossier = preparer(scenario)
    resultat = instruire_avec_agent(session_test, dossier, reglement, fournisseurs_demo)
    assert resultat.conclu
    assert resultat.tours == 6
    assert resultat.decision.statut_regles is statut
    assert resultat.decision.statut_propose_llm is statut
    assert resultat.decision.garde_fou_declenche is False
    assert "### Points forts du dossier" in resultat.decision.rapport
    assert any(c["categorie"] == "lettre" for c in resultat.decision.conseils) or (
        scenario is demo.dossier_sans_lettre
    )


def test_hors_delai_non_recevable(
    preparer: FabriqueDossier,
    session_test: Session,
    reglement: Reglement,
    fournisseurs_demo: Fournisseurs,
) -> None:
    dossier = preparer(date_envoi="2026-10-19T00:00:01+02:00")
    d_ = instruire_avec_agent(session_test, dossier, reglement, fournisseurs_demo).decision
    assert d_.statut_regles is Verdict.NON_RECEVABLE
    assert "## Verdict : ❌ Non recevable" in d_.rapport
    assert "après la date limite" in d_.rapport
