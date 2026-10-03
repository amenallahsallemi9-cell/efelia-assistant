"""Repérage déterministe des tentatives d'injection de prompt dans les documents.

Le contenu des documents est toujours traité comme une donnée. Ce module signale en
plus les passages qui ressemblent à des consignes adressées à une IA, pour que l'agent
les mentionne dans ses motifs (et pour que l'humain les voie).
"""

import re
from dataclasses import dataclass

from app.domain.noms import sans_accents

_MOTIFS = tuple(
    re.compile(motif, re.IGNORECASE)
    for motif in (
        r"ignore[rz]?\s+(?:toutes?\s+)?(?:tes|les|vos|ces)\s+(?:r[eè]gles|instructions|consignes)",
        r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above)\s+instructions",
        r"(?:d[ée]clare|consid[eè]re|marque)[rz]?\s+(?:ce|le)\s+dossier\s+(?:comme\s+)?recevable",
        r"(?:instruction|consigne|message)s?\s+(?:pour|[àa]|destin[ée]e?s?\s+[àa])\s+"
        r"l['’]?\s*(?:assistant|ia|agent|intelligence artificielle|llm)",
        r"\b(?:system\s+prompt|prompt\s+syst[eè]me)\b",
        r"\btu\s+es\s+(?:d[ée]sormais|maintenant)\b",
        r"\byou\s+are\s+now\b",
        r"\boublie[rz]?\s+(?:tes|les|vos)\s+(?:r[eè]gles|instructions|consignes)",
    )
)


@dataclass(frozen=True)
class AlerteInjection:
    """Passage suspect, avec sa page."""

    page: int
    extrait: str


def detecter_injections(texte: str, page: int, contexte: int = 60) -> list[AlerteInjection]:
    """Passages ressemblant à des instructions adressées à une IA."""
    alertes: list[AlerteInjection] = []
    vus: set[int] = set()
    normalise = sans_accents(texte)
    # Les positions ne sont transposables que si la normalisation garde la longueur.
    source = texte if len(normalise) == len(texte) else normalise
    for motif in _MOTIFS:
        for correspondance in motif.finditer(normalise):
            if any(abs(correspondance.start() - debut) < contexte for debut in vus):
                continue
            vus.add(correspondance.start())
            debut = max(0, correspondance.start() - contexte)
            fin = min(len(source), correspondance.end() + contexte)
            extrait = " ".join(source[debut:fin].split())
            alertes.append(AlerteInjection(page=page, extrait=extrait))
    return alertes
