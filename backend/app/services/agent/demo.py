"""Agent scripté du mode démo (FakeLLM sans clé) : suit la procédure, sans LLM.

Il enchaîne les outils comme le ferait un agent réel (plusieurs appels par tour),
propose une décision déduite des résultats et rédige un rapport à partir des données
lues. Il permet de voir toute la chaîne fonctionner hors ligne.
"""

import json
import re
from collections.abc import Sequence
from typing import Any

from app.providers.base import AppelOutil, Message, ReponseLLM

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

PLAN: tuple[tuple[str, tuple[tuple[str, dict[str, Any]], ...]], ...] = (
    ("Je lis la fiche et la liste des pièces.", (("lire_fiche", {}),)),
    (
        "Je vérifie l'éligibilité, le format et les pièces.",
        (("verifier_eligibilite", {}), ("verifier_format", {}), ("verifier_pieces", {})),
    ),
    (
        "Je lis la lettre, le CV et les relevés.",
        (
            ("lire_piece", {"type_piece": "lettre_motivation"}),
            ("lire_piece", {"type_piece": "cv"}),
            ("lire_piece", {"type_piece": "releve_notes"}),
        ),
    ),
    (
        "Je vérifie la cohérence et je consulte le règlement sur la lettre.",
        (
            ("verifier_coherence", {}),
            ("rechercher_reglement", {"question": "Que doit contenir la lettre de motivation ?"}),
        ),
    ),
)


def _resultats(messages: Sequence[Message]) -> dict[str, list[dict[str, Any]]]:
    """Résultats d'outils déjà reçus, regroupés par nom d'outil."""
    noms = {a.id: a.nom for m in messages if m.role == "assistant" for a in m.appels_outils}
    resultats: dict[str, list[dict[str, Any]]] = {}
    for message in messages:
        if message.role == "tool" and message.id_appel in noms:
            resultats.setdefault(noms[message.id_appel], []).append(json.loads(message.contenu))
    return resultats


def _controles(resultats: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [
        c
        for nom in (
            "verifier_eligibilite",
            "verifier_format",
            "verifier_pieces",
            "verifier_coherence",
        )
        for r in resultats.get(nom, [])
        for c in r.get("controles", [])
    ]


def _statut(controles: list[dict[str, Any]]) -> str:
    effets = {
        c["consequence"]
        for c in controles
        if c["resultat"] == "NON_CONFORME" and c["consequence"] != "AVERTISSEMENT"
    }
    if "NON_RECEVABLE" in effets:
        return "NON_RECEVABLE"
    return "A_COMPLETER" if "A_COMPLETER" in effets else "RECEVABLE"


def _piece(resultats: dict[str, list[dict[str, Any]]], type_piece: str) -> dict[str, Any]:
    for resultat in resultats.get("lire_piece", []):
        if resultat.get("type_piece") == type_piece and resultat.get("present"):
            return resultat
    return {}


def _decision(dossier_id: str, resultats: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    controles = _controles(resultats)
    motifs = [
        {
            "message": c["message"],
            "page": next((p["page"] for p in c["preuves"] if p.get("page")), None),
            "extrait": next((p["extrait"] for p in c["preuves"] if p.get("extrait")), None),
        }
        for c in controles
        if c["resultat"] == "NON_CONFORME" and c["consequence"] != "AVERTISSEMENT"
    ]
    for alerte in (resultats.get("lire_fiche") or [{}])[0].get("alertes_injection", []):
        motifs.append(
            {
                "message": "Consigne adressée à une IA détectée dans le dossier : ignorée.",
                "page": alerte["page"],
                "extrait": alerte["extrait"][:300],
            }
        )
    return {
        "dossier_id": dossier_id,
        "statut": _statut(controles),
        "motifs": motifs,
        "conseils": _conseils(resultats, controles),
    }


def _conseils(
    resultats: dict[str, list[dict[str, Any]]], controles: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    conseils: list[dict[str, Any]] = []
    lettre = _piece(resultats, "lettre_motivation")
    donnees = lettre.get("donnees", {})
    page_lettre = (lettre.get("pages") or [None])[0]
    manquants = [
        t for t in ("formation", "parcours", "projet") if not (donnees.get(t) or {}).get("present")
    ]
    if lettre and manquants:
        conseils.append(
            {
                "categorie": "lettre",
                "texte": "Développez explicitement : "
                + ", ".join(manquants)
                + " (le règlement demande formation, parcours et projet).",
                "page": page_lettre,
            }
        )
    elif lettre:
        conseils.append(
            {
                "categorie": "lettre",
                "texte": "La lettre couvre formation, parcours et projet : reliez davantage "
                "votre projet à l'intelligence artificielle et à la formation suivie.",
                "page": page_lettre,
            }
        )
    cv = _piece(resultats, "cv")
    if cv:
        nb = cv.get("donnees", {}).get("nb_pages")
        conseils.append(
            {
                "categorie": "cv",
                "texte": f"CV de {nb} page(s) : mettez en avant les projets en IA avec un lien "
                "vérifiable (GitHub, portfolio)."
                + (" Réduisez-le à 2 pages maximum." if nb and nb > 2 else ""),
                "page": (cv.get("pages") or [None])[0],
            }
        )
    for controle in controles:
        if controle["resultat"] == "NON_CONFORME" and controle["consequence"] == "A_COMPLETER":
            conseils.append({"categorie": "pieces", "texte": controle["message"], "page": None})
    return conseils


def _rapport(resultats: dict[str, list[dict[str, Any]]]) -> str:
    releve = _piece(resultats, "releve_notes").get("donnees", {})
    lettre = _piece(resultats, "lettre_motivation").get("donnees", {})
    cv = _piece(resultats, "cv").get("donnees", {})
    forts = []
    if releve.get("moyenne_generale") is not None:
        mention = f", mention {releve['mention']}" if releve.get("mention") else ""
        moyenne = str(releve["moyenne_generale"]).replace(".", ",")
        forts.append(f"- Résultats académiques : moyenne de {moyenne}/20{mention}.")
    if cv.get("projets"):
        forts.append(f"- Projets présentés dans le CV : {', '.join(cv['projets'][:2])}.")
    if lettre.get("mentionne_ia"):
        forts.append("- La lettre relie la candidature à l'intelligence artificielle.")
    lignes = [
        "### Points forts du dossier",
        *(forts or ["- Aucun point fort identifié automatiquement."]),
    ]
    lignes += [
        "",
        "### Conseils pour la lettre de motivation",
        "- Illustrez chaque thème (formation, parcours, projet) par un exemple concret.",
        "",
        "### Conseils pour le CV",
        "- Priorisez les expériences et projets liés à l'IA, avec des résultats mesurables.",
        "",
        "### Pièces à ajouter ou à corriger",
        "- Voir la liste établie par les règles ci-dessus.",
        "",
        "_Rapport rédigé en mode démo (agent scripté, sans LLM)._",
    ]
    return "\n".join(lignes)


def repondre_agent_demo(messages: Sequence[Message]) -> ReponseLLM:
    """Prochain pas de l'agent scripté."""
    premier = next((m.contenu for m in messages if m.role == "user"), "")
    correspondance = _UUID.search(premier)
    dossier_id = correspondance.group() if correspondance else ""
    etape = sum(1 for m in messages if m.role == "assistant" and m.appels_outils)
    if etape < len(PLAN):
        plan, appels = PLAN[etape]
        return ReponseLLM(
            plan=plan,
            appels_outils=tuple(
                AppelOutil(
                    f"demo_{etape}_{i}",
                    nom,
                    json.dumps(
                        {
                            **({} if nom == "rechercher_reglement" else {"dossier_id": dossier_id}),
                            **args,
                        }
                    ),
                )
                for i, (nom, args) in enumerate(appels)
            ),
        )
    resultats = _resultats(messages)
    if etape == len(PLAN):
        return ReponseLLM(
            plan="J'enregistre ma proposition de décision.",
            appels_outils=(
                AppelOutil(
                    "demo_decision",
                    "enregistrer_decision",
                    json.dumps(_decision(dossier_id, resultats), ensure_ascii=False),
                ),
            ),
        )
    return ReponseLLM(texte=_rapport(resultats))
