"""Boucle de l'agent (tool calling) et enregistrement de la décision.

Déroulé : messages + outils → appels d'outils exécutés → résultats renvoyés en messages
`tool` → … jusqu'à une réponse sans appel d'outil, avec au plus 12 tours.

Quoi qu'il arrive (agent qui ne conclut pas, fournisseur en panne, statut forcé), une
décision est enregistrée avec le statut des RÈGLES, et chaque étape est tracée dans
`traces_agent` (journal d'audit).
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.modeles import Decision, Dossier, TraceAgent
from app.domain.regles import Reglement
from app.providers import Fournisseurs
from app.providers.base import ErreurFournisseur, Message
from app.services.agent.contexte import ContexteAgent, controle_vers_dict
from app.services.agent.garde_fou import appliquer_garde_fou, retirer_predictions
from app.services.agent.outils import alertes_injection, executer_outil, outils_pour_llm
from app.services.agent.prompts import demande_initiale, prompt_systeme
from app.services.agent.rapport import generer_rapport

logger = logging.getLogger(__name__)

MAX_TOURS = 12
MAX_CARACTERES_TRACE = 4000


@dataclass(frozen=True)
class ResultatInstruction:
    """Issue de la boucle (utile aux tests et aux journaux)."""

    decision: Decision
    tours: int
    conclu: bool


class _Traceur:
    """Écrit le journal d'audit au fil de l'eau."""

    def __init__(self, session: Session, dossier: Dossier) -> None:
        self._session = session
        self._dossier = dossier
        self._ordre = 0

    def ecrire(
        self,
        outil: str,
        arguments: dict[str, Any],
        resultat: Any,
        duree_ms: int,
        tokens: int | None = None,
    ) -> None:
        self._ordre += 1
        self._session.add(
            TraceAgent(
                dossier_id=self._dossier.id,
                ordre=self._ordre,
                outil=outil,
                arguments=arguments,
                resultat=_tronquer(resultat),
                duree_ms=duree_ms,
                tokens=tokens,
            )
        )


def _tronquer(valeur: Any) -> Any:
    texte = json.dumps(valeur, ensure_ascii=False, default=str)
    if len(texte) <= MAX_CARACTERES_TRACE:
        return valeur
    return {"tronque": True, "apercu": texte[:MAX_CARACTERES_TRACE]}


def _arguments(brut: str) -> dict[str, Any]:
    try:
        valeur = json.loads(brut or "{}")
    except json.JSONDecodeError:
        return {"brut": brut[:500]}
    return valeur if isinstance(valeur, dict) else {"brut": brut[:500]}


def _ms(debut: float) -> int:
    return round((time.perf_counter() - debut) * 1000)


def instruire_avec_agent(
    session: Session,
    dossier: Dossier,
    reglement: Reglement,
    fournisseurs: Fournisseurs,
    max_tours: int = MAX_TOURS,
) -> ResultatInstruction:
    """Fait instruire le dossier par l'agent et enregistre la décision (garde-fou compris)."""
    session.execute(delete(TraceAgent).where(TraceAgent.dossier_id == dossier.id))
    contexte = ContexteAgent(session, dossier, reglement, fournisseurs)
    traceur = _Traceur(session, dossier)
    outils = outils_pour_llm()
    messages = [
        Message("system", prompt_systeme(reglement)),
        Message("user", demande_initiale(str(dossier.id))),
    ]
    texte_final: str | None = None
    note: str | None = None
    tours = 0

    for tours in range(1, max_tours + 1):
        debut = time.perf_counter()
        try:
            reponse = fournisseurs.llm.discuter(messages, outils)
        except ErreurFournisseur as exc:
            logger.warning(
                "Agent indisponible, repli déterministe",
                exc_info=exc,
                extra={"dossier_id": str(dossier.id), "tour": tours},
            )
            traceur.ecrire("llm", {"tour": tours}, {"erreur": str(exc)}, _ms(debut))
            note = "Agent LLM indisponible : rapport établi uniquement à partir des règles."
            break
        traceur.ecrire(
            "llm",
            {"tour": tours},
            {
                "plan": reponse.plan,
                "appels": [a.nom for a in reponse.appels_outils],
                "texte": (reponse.texte or "")[:500] or None,
            },
            _ms(debut),
            reponse.tokens,
        )
        if not reponse.appels_outils:
            texte_final = reponse.texte or ""
            break
        messages.append(
            Message("assistant", reponse.texte or "", reponse.appels_outils, plan=reponse.plan)
        )
        for appel in reponse.appels_outils:
            debut = time.perf_counter()
            resultat = executer_outil(contexte, appel)
            traceur.ecrire(appel.nom, _arguments(appel.arguments), resultat, _ms(debut))
            messages.append(
                Message("tool", json.dumps(resultat, ensure_ascii=False), id_appel=appel.id)
            )
    else:
        note = f"L'agent n'a pas conclu en {max_tours} tours : rapport établi à partir des règles."

    conclu = texte_final is not None
    decision = _enregistrer(contexte, texte_final, note)
    logger.info(
        "Instruction terminée",
        extra={
            "dossier_id": str(dossier.id),
            "etape": "INSTRUIT",
            "statut": decision.statut_regles.value,
            "tour": tours,
        },
    )
    return ResultatInstruction(decision=decision, tours=tours, conclu=conclu)


def _enregistrer(contexte: ContexteAgent, texte_final: str | None, note: str | None) -> Decision:
    """Décision finale : statut des règles, proposition du LLM, rapport."""
    instruction = contexte.instruction()
    proposition = contexte.proposition
    statut, garde_fou = appliquer_garde_fou(
        instruction.statut, proposition.statut if proposition else None
    )
    analyse, nb_predictions = retirer_predictions(texte_final or "")
    conseils = []
    for conseil in proposition.conseils if proposition else []:
        texte, retirees = retirer_predictions(conseil["texte"])
        nb_predictions += retirees
        if texte:
            conseils.append({**conseil, "texte": texte, "source": "agent"})
    alertes = alertes_injection(contexte)

    avertissements = [controle_vers_dict(c) for c in instruction.avertissements]
    avertissements += [
        {
            "code": "injection_prompt",
            "categorie": "securite",
            "libelle": "Tentative d'injection de prompt ignorée",
            "resultat": "NON_CONFORME",
            "consequence": "AVERTISSEMENT",
            "message": "Un passage du dossier s'adresse à une IA ; "
            "il a été traité comme une donnée.",
            "preuves": [{"source": "document", "page": a["page"], "extrait": a["extrait"]}],
        }
        for a in alertes
    ]
    if nb_predictions:
        avertissements.append(
            {
                "code": "prediction_retiree",
                "categorie": "securite",
                "libelle": "Prédiction retirée du rapport",
                "resultat": "NON_CONFORME",
                "consequence": "AVERTISSEMENT",
                "message": f"{nb_predictions} phrase(s) estimant la décision du jury "
                "ont été retirées.",
                "preuves": [],
            }
        )

    rapport = generer_rapport(
        contexte.dossier,
        instruction,
        alertes_injection=alertes,
        statut_propose=proposition.statut if proposition else None,
        garde_fou=garde_fou,
        analyse_agent=analyse,
        conseils=conseils,
        note=note,
    )
    decision = Decision(
        dossier_id=contexte.dossier.id,
        statut_regles=statut,
        statut_propose_llm=proposition.statut if proposition else None,
        garde_fou_declenche=garde_fou,
        controles=[controle_vers_dict(c) for c in instruction.controles],
        # Motifs des règles (font foi), puis explications rédigées par l'agent.
        motifs=[{"source": "regles", **controle_vers_dict(c)} for c in instruction.motifs]
        + [{"source": "agent", **m} for m in (proposition.motifs if proposition else [])],
        avertissements=avertissements,
        conseils=conseils,
        rapport=rapport,
        modele=contexte.fournisseurs.llm.nom_modele,
    )
    contexte.session.add(decision)
    contexte.session.flush()
    return decision
