"""Garde-fous appliqués à la sortie du LLM.

1. Le statut final est celui des règles ; un écart avec la proposition du LLM est tracé.
2. Toute phrase qui prédit la décision du jury (chances, probabilité, « vous serez
   retenu·e »…) est retirée du texte du LLM, quoi qu'en dise le prompt.
"""

import re

from app.domain.modeles import Verdict
from app.domain.noms import sans_accents

_PREDICTIONS = tuple(
    re.compile(motif, re.IGNORECASE)
    for motif in (
        r"\bchances?\b",
        r"\bprobabilit",
        r"\bprobable(?:ment)?\b",
        r"\d+\s*%",
        r"\b(?:serez|sera|seras|etre|soit)\s+(?:tres\s+)?(?:probablement\s+)?(?:retenu|selectionne|laureat|admis)",
        r"\b(?:obtiendr|decrocher)\w*\s+(?:la|cette)\s+bourse",
        r"\bfavori\w*\b",
        r"\bpronosti",
    )
)


def appliquer_garde_fou(
    statut_regles: Verdict, statut_propose: Verdict | None
) -> tuple[Verdict, bool]:
    """Statut final (toujours celui des règles) et déclenchement du garde-fou."""
    return statut_regles, statut_propose is not None and statut_propose is not statut_regles


def contient_prediction(phrase: str) -> bool:
    """Vrai si la phrase estime l'issue de la sélection par le jury."""
    normalisee = sans_accents(phrase)
    return any(motif.search(normalisee) for motif in _PREDICTIONS)


def retirer_predictions(texte: str) -> tuple[str, int]:
    """Supprime les phrases prédictives ; renvoie le texte nettoyé et le nombre retiré."""
    lignes_sortie: list[str] = []
    retirees = 0
    for ligne in texte.splitlines():
        if ligne.lstrip().startswith("#"):
            lignes_sortie.append(ligne)
            continue
        morceaux = re.split(r"(?<=[.!?])\s+", ligne)
        gardes = []
        for morceau in morceaux:
            if morceau.strip() and contient_prediction(morceau):
                retirees += 1
            else:
                gardes.append(morceau)
        nouvelle = " ".join(gardes).rstrip()
        # Une puce vidée de son contenu disparaît entièrement.
        if nouvelle.strip() in {"-", "*", ""} and ligne.strip():
            continue
        lignes_sortie.append(nouvelle)
    return "\n".join(lignes_sortie).strip(), retirees
