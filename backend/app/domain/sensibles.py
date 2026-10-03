"""Détection déterministe des justificatifs sensibles (sociaux, handicap).

Exécutée dès l'extraction, AVANT tout stockage ou appel au LLM : le texte d'une page
détectée comme sensible n'est ni conservé, ni envoyé au LLM, ni indexé (RGPD). Seul le
type de document est retenu.

Méthode : score de mots-clés pondérés. Un seul indice faible ne suffit pas (un CV peut
mentionner « MDPH ») ; une attestation sur l'honneur de non-cumul n'est jamais sensible.
"""

import re
from dataclasses import dataclass

from app.domain.modeles import TypePiece
from app.domain.noms import normaliser

SEUIL = 2

# (expression régulière sur le texte normalisé, poids)
_INDICES_SOCIAUX: tuple[tuple[str, int], ...] = (
    (r"avis d (?:impot|imposition)", 2),
    (r"revenu fiscal de reference", 2),
    (r"numero fiscal", 2),
    (r"impot sur le revenu", 1),
    (r"\biban\b", 2),
    (r"\bfr\d{2}(?: ?\d{4}){5}", 2),  # IBAN français
    (r"\bbic\b", 1),
    (r"releve (?:de compte|bancaire|d identite bancaire)", 1),
    (r"\bsolde\b", 1),
    (r"bulletin de (?:paie|salaire)", 2),
    (r"net a payer", 2),
    (r"salaire (?:brut|net)", 1),
    (r"notification (?:conditionnelle |definitive )?(?:d attribution )?de bourse", 2),
    (r"attestation d attribution de bourse", 2),
    (r"\bechelon\b", 1),
)

_INDICES_HANDICAP: tuple[tuple[str, int], ...] = (
    (r"\bmdph\b", 1),
    (r"maison departementale des personnes handicapees", 2),
    (r"\brqth\b", 1),
    (r"reconnaissance de la qualite de travailleur handicape", 2),
    (r"carte mobilite inclusion", 2),
    (r"\bcmi\b", 1),
    (r"taux d incapacite", 2),
    (r"certificat medical", 2),
    (r"\bdiagnostic\b", 1),
    (r"\bpathologie\b", 1),
    (r"amenagement(?:s)? (?:des examens|d etudes)", 1),
)

_ATTESTATION_HONNEUR = re.compile(r"sur l honneur")
_NON_CUMUL = re.compile(r"\b(?:non )?cumul")


@dataclass(frozen=True)
class Detection:
    """Résultat de la détection sur une page."""

    type_piece: TypePiece
    score: int

    @property
    def confiance(self) -> float:
        """Confiance heuristique, croissante avec le score (plafonnée à 0,95)."""
        return min(0.95, 0.5 + 0.1 * self.score)


def _score(texte: str, indices: tuple[tuple[str, int], ...]) -> int:
    return sum(poids for motif, poids in indices if re.search(motif, texte))


def detecter_page_sensible(texte: str) -> Detection | None:
    """Retourne le type de justificatif sensible détecté, ou None si la page est ordinaire."""
    normalise = normaliser(texte)
    if not normalise:
        return None
    if _ATTESTATION_HONNEUR.search(normalise) and _NON_CUMUL.search(normalise):
        return None
    social = _score(normalise, _INDICES_SOCIAUX)
    handicap = _score(normalise, _INDICES_HANDICAP)
    if max(social, handicap) < SEUIL:
        return None
    if handicap > social:
        return Detection(TypePiece.JUSTIFICATIF_HANDICAP, handicap)
    return Detection(TypePiece.JUSTIFICATIF_SOCIAL, social)
