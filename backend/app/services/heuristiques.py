"""Lecture heuristique (mots-clés, expressions régulières), sans LLM.

Double usage :
- secours quand le LLM échoue ou hésite (classification, lecture) ;
- moteur du FakeProvider, pour un mode démo réaliste et des tests déterministes.
"""

import re
from typing import Any

from app.domain.coherence import normaliser_annee
from app.domain.modeles import TypePiece
from app.domain.noms import normaliser

# (type, motifs sur le texte normalisé, poids). Les titres pèsent plus que le vocabulaire.
_INDICES_TYPES: tuple[tuple[TypePiece, tuple[tuple[str, float], ...]], ...] = (
    (
        TypePiece.CERTIFICAT_SCOLARITE,
        (
            (r"certificat de scolarite", 3),
            (r"attestation d inscription", 3),
            (r"(?:est|etre) (?:regulierement )?inscrit", 1),
            (r"annee universitaire", 0.5),
            (r"n(?:o|°)? etudiant|numero etudiant", 0.5),
        ),
    ),
    (
        TypePiece.CV,
        (
            (r"curriculum vitae|\bcv\b", 3),
            (r"\bcompetences\b", 1),
            (r"\bexperiences?\b", 1),
            (r"\blangues\b", 0.5),
            (r"centres d interet", 1),
            (r"github|linkedin", 0.5),
        ),
    ),
    (
        TypePiece.RELEVE_NOTES,
        (
            (r"releve de notes|releve des notes|bulletin de notes", 3),
            (r"\bects\b", 1),
            (r"moyenne generale", 1),
            (r"/ ?20\b", 0.5),
        ),
    ),
    (
        TypePiece.LETTRE_MOTIVATION,
        (
            (r"lettre de motivation", 3),
            (r"madame,? monsieur", 1),
            (r"salutations distinguees|l expression de mes", 1),
            (r"\bje souhaite\b|\bma candidature\b|\bmon projet\b", 0.5),
        ),
    ),
    (
        TypePiece.ATTESTATION_NON_CUMUL,
        (
            (r"attestation sur l honneur", 2),
            (r"non cumul|ne pas cumuler", 2),
            (r"je soussigne", 0.5),
        ),
    ),
    (
        TypePiece.LETTRE_RECOMMANDATION,
        (
            (r"lettre de recommandation", 3),
            (r"je recommande|recommande (?:sa|cette) candidature", 1.5),
            (r"j ai encadre|j ai eu (?:le plaisir|l occasion)", 1),
        ),
    ),
)


def classer_par_mots_cles(texte: str) -> tuple[TypePiece, float]:
    """Type de pièce le plus probable et confiance heuristique (0 à 0,9)."""
    normalise = normaliser(texte)
    scores = {
        type_piece: sum(poids for motif, poids in indices if re.search(motif, normalise))
        for type_piece, indices in _INDICES_TYPES
    }
    meilleur, score = max(scores.items(), key=lambda element: element[1])
    if score < 1.5:
        return TypePiece.AUTRE, 0.3
    return meilleur, min(0.9, 0.4 + score / 10)


# --------------------------------------------------------------------------- lecture


def _champ(texte: str, *etiquettes: str) -> str | None:
    for etiquette in etiquettes:
        correspondance = re.search(rf"(?<!\w)(?:{etiquette})\s*:\s*(.+)", texte, re.IGNORECASE)
        if correspondance:
            return correspondance.group(1).strip()
    return None


def _ligne_avec(texte: str, motif: str) -> str | None:
    for ligne in texte.splitlines():
        if re.search(motif, normaliser(ligne)):
            return ligne.strip()
    return None


def _phrase_avec(texte: str, motifs: tuple[str, ...]) -> str | None:
    phrases = re.split(r"(?<=[.!?])\s+", " ".join(texte.split()))
    for phrase in phrases:
        if any(re.search(motif, normaliser(phrase)) for motif in motifs):
            return phrase[:300]
    return None


def _section(texte: str, titre: str) -> list[str]:
    """Lignes sous un titre en majuscules, jusqu'à la ligne vide ou au titre suivant."""
    lignes = texte.splitlines()
    for i, ligne in enumerate(lignes):
        if normaliser(ligne) == titre:
            contenu = []
            for suivante in lignes[i + 1 :]:
                if not suivante.strip() or (suivante.isupper() and len(suivante) > 3):
                    break
                contenu.append(suivante.strip()[:200])
            return contenu
    return []


def _lire_certificat(texte: str) -> dict[str, Any]:
    annee = normaliser_annee(_ligne_avec(texte, r"annee universitaire") or texte)
    return {
        "nom": _champ(texte, "Nom"),
        "prenom": _champ(texte, r"Pr[ée]noms?(?:\(s\))?"),
        "etablissement": _ligne_avec(texte, r"universite|ecole|institut"),
        "formation": _champ(texte, r"Formation|Dipl[ôo]me"),
        "annee_universitaire": annee,
        "extrait": _ligne_avec(texte, r"inscrit"),
    }


def _lire_cv(texte: str) -> dict[str, Any]:
    competences = [
        c.strip() for ligne in _section(texte, "competences") for c in ligne.split(",") if c.strip()
    ]
    return {
        "competences": competences[:30],
        "projets": _section(texte, "projets")[:30],
        "experiences": _section(texte, "experiences")[:30],
        "liens": sorted(
            set(
                re.findall(
                    r"(?:https?://)?(?:github\.com|gitlab\.com|linkedin\.com)/[\w\-./]+", texte
                )
            )
            | set(re.findall(r"\b[\w\-]+\.(?:dev|io|me)\b", texte))
        )[:30],
    }


def _nombre(texte: str | None) -> float | None:
    if not texte:
        return None
    correspondance = re.search(r"\d+(?:[.,]\d+)?", texte)
    return float(correspondance.group().replace(",", ".")) if correspondance else None


def _lire_releve(texte: str) -> dict[str, Any]:
    moyenne = _nombre(_champ(texte, r"Moyenne g[ée]n[ée]rale"))
    credits = re.search(r"cr[ée]dits? ects[^\d]*(\d+)", texte, re.IGNORECASE)
    mention = re.search(r"mention\s+(tr[èe]s bien|bien|assez bien|passable)", texte, re.IGNORECASE)
    ligne_annee = _ligne_avec(texte, r"annee universitaire|\b20\d\d ?[-/] ?(?:20)?\d\d\b")
    return {
        "annee": normaliser_annee(ligne_annee),
        "moyenne_generale": moyenne if moyenne is not None and moyenne <= 20 else None,
        "mention": mention.group(1).capitalize() if mention else None,
        "credits_ects": int(credits.group(1)) if credits else None,
        "extrait": ligne_annee,
    }


_THEMES_LETTRE = {
    "formation": (r"\binscrit|\bma formation\b|cette formation|\bmaster\b|\bm1\b|\bm2\b",),
    "parcours": (r"\bparcours\b|\bapres (?:une|un|mon|ma)\b|\blicence\b|\bstage\b",),
    "projet": (
        r"\bmon projet\b|\bprojet professionnel\b|\bje souhaite\b|\bambition\b|\bdevenir\b",
    ),
}


def _lire_lettre(texte: str) -> dict[str, Any]:
    resultat: dict[str, Any] = {}
    for theme, motifs in _THEMES_LETTRE.items():
        phrase = _phrase_avec(texte, motifs)
        resultat[theme] = {"present": phrase is not None, "extrait": phrase}
    resultat["mentionne_ia"] = bool(
        re.search(
            r"intelligence artificielle|\bia\b|apprentissage (?:automatique|profond)",
            normaliser(texte),
        )
    )
    return resultat


def _lire_attestation(texte: str) -> dict[str, Any]:
    lieu_date = re.search(r"fait [àa] .{2,60}?,? le .{4,40}", texte, re.IGNORECASE)
    bourse = re.search(
        r"b[ée]n[ée]ficier de la bourse suivante\s*:\s*([^.\n]+)"
        r"|je per[çc]ois (?:la |une )?(bourse [^.\n]+)",
        texte,
        re.IGNORECASE,
    )
    return {
        "mention_signature": bool(lieu_date)
        or bool(re.search(r"\bsignature\b|sign[ée] [ée]lectroniquement", texte, re.I)),
        "lieu_date": lieu_date.group().strip() if lieu_date else None,
        "bourse_declaree": next((g.strip() for g in bourse.groups() if g), None)
        if bourse
        else None,
        "extrait": _phrase_avec(texte, (r"sur l honneur",)),
    }


def _lire_recommandation(texte: str) -> dict[str, Any]:
    premiere = next((ligne.strip() for ligne in texte.splitlines()[1:] if ligne.strip()), None)
    return {
        "auteur": premiere.split(",")[0] if premiere else None,
        "fonction_auteur": ", ".join(premiere.split(",")[1:]).strip() or None if premiere else None,
        "extrait": _phrase_avec(texte, (r"recommande",)),
    }


_LECTEURS = {
    TypePiece.CERTIFICAT_SCOLARITE: _lire_certificat,
    TypePiece.CV: _lire_cv,
    TypePiece.RELEVE_NOTES: _lire_releve,
    TypePiece.LETTRE_MOTIVATION: _lire_lettre,
    TypePiece.ATTESTATION_NON_CUMUL: _lire_attestation,
    TypePiece.LETTRE_RECOMMANDATION: _lire_recommandation,
}


_MARQUEUR_PAGE = re.compile(r"^--- page \d+ ---$", re.MULTILINE)


def lire_par_heuristique(type_piece: TypePiece, texte: str) -> dict[str, Any]:
    """Données structurées extraites sans LLM (même forme que les schémas de lecture)."""
    lecteur = _LECTEURS.get(type_piece)
    return lecteur(_MARQUEUR_PAGE.sub("", texte)) if lecteur else {}
