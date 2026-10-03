"""Rapport d'instruction en Markdown.

L'en-tête (verdict, motifs et preuves, points de vigilance, pièces à ajouter) est
généré à partir des règles : il est toujours exact. L'analyse rédigée par l'agent
(points forts, conseils) vient ensuite, nettoyée de toute prédiction.
"""

from collections.abc import Sequence
from typing import Any

from app.db.modeles import Dossier
from app.domain.instruction import Instruction
from app.domain.modeles import Verdict
from app.domain.regles import Controle, Preuve, Resultat

LIBELLES_VERDICT = {
    Verdict.RECEVABLE: (
        "✅",
        "Recevable",
        "Le dossier est complet et conforme : il peut être examiné par le jury.",
    ),
    Verdict.A_COMPLETER: (
        "⚠️",
        "À compléter",
        "Le dossier doit être complété ou corrigé avant d'être examiné.",
    ),
    Verdict.NON_RECEVABLE: (
        "❌",
        "Non recevable",
        "Le dossier ne remplit pas une condition d'éligibilité ou de délai.",
    ),
}
CATEGORIES_CONSEIL = {"lettre": "Lettre", "cv": "CV", "pieces": "Pièces", "general": "Général"}
AVERTISSEMENT_JURY = (
    "_Ce verdict porte uniquement sur la recevabilité. Il ne préjuge en rien de la décision "
    "du jury, qui n'est pas prévisible._"
)


def _preuve(preuve: Preuve) -> str:
    morceaux = []
    if preuve.page is not None:
        morceaux.append(f"page {preuve.page}")
    if preuve.extrait:
        morceaux.append(f"« {preuve.extrait} »")
    elif preuve.source == "fiche":
        morceaux.append("fiche déclarative")
    return " : ".join(morceaux)


def _ligne(controle: Controle) -> str:
    preuves = "; ".join(p for p in (_preuve(x) for x in controle.preuves) if p)
    return f"- **{controle.libelle}** — {controle.message}" + (f" _({preuves})_" if preuves else "")


def generer_rapport(
    dossier: Dossier,
    instruction: Instruction,
    *,
    alertes_injection: Sequence[dict[str, Any]],
    statut_propose: Verdict | None,
    garde_fou: bool,
    analyse_agent: str | None,
    conseils: Sequence[dict[str, Any]],
    note: str | None = None,
) -> str:
    """Rapport complet ; les sections déterministes précèdent l'analyse de l'agent."""
    icone, libelle, explication = LIBELLES_VERDICT[instruction.statut]
    lignes = [
        f"# Rapport d'instruction — {dossier.prenom} {dossier.nom.upper()}",
        "",
        f"## Verdict : {icone} {libelle}",
        "",
        explication,
        "",
        AVERTISSEMENT_JURY,
    ]
    if garde_fou and statut_propose is not None:
        lignes += [
            "",
            f"> **Garde-fou déclenché** — l'agent proposait « {statut_propose.value} ». "
            f"Le statut calculé par les règles (« {instruction.statut.value} ») s'applique.",
        ]
    if note:
        lignes += ["", f"> {note}"]

    if instruction.motifs:
        lignes += ["", "## Motifs", "", *(_ligne(c) for c in instruction.motifs)]

    vigilance = [_ligne(c) for c in instruction.avertissements]
    vigilance += [
        f"- **Tentative d'injection de prompt ignorée** — un passage s'adresse à une IA "
        f"_(page {a['page']} : « {a['extrait']} »)_"
        for a in alertes_injection
    ]
    if vigilance:
        lignes += ["", "## Points de vigilance", "", *vigilance]

    a_fournir = [
        c
        for c in instruction.controles
        if c.resultat is Resultat.NON_CONFORME and c.effet is not None
    ]
    if a_fournir:
        lignes += [
            "",
            "## Pièces à ajouter ou à corriger",
            "",
            *(f"- {c.message}" for c in a_fournir),
        ]

    if conseils:
        lignes += ["", "## Conseils", ""]
        for conseil in conseils:
            page = f" _(page {conseil['page']})_" if conseil.get("page") else ""
            categorie = CATEGORIES_CONSEIL.get(str(conseil.get("categorie")), "Général")
            lignes.append(f"- **{categorie}** — {conseil['texte']}{page}")

    lignes += ["", "## Analyse de l'agent", ""]
    lignes.append(
        analyse_agent.strip()
        if analyse_agent and analyse_agent.strip()
        else "_Aucune analyse rédigée._"
    )
    return "\n".join(lignes) + "\n"
