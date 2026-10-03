"""Vocabulaire métier partagé par toutes les couches (aucune dépendance externe)."""

from enum import StrEnum


class StatutPipeline(StrEnum):
    """Étape atteinte par un dossier dans le pipeline de traitement."""

    RECU = "RECU"
    EXTRAIT = "EXTRAIT"
    CLASSE = "CLASSE"
    LU = "LU"
    INDEXE = "INDEXE"
    INSTRUIT = "INSTRUIT"
    ERREUR = "ERREUR"


class Verdict(StrEnum):
    """Recevabilité du dossier. Ne préjuge jamais de la décision du jury."""

    RECEVABLE = "RECEVABLE"
    A_COMPLETER = "A_COMPLETER"
    NON_RECEVABLE = "NON_RECEVABLE"


class TypePiece(StrEnum):
    """Types de pièces reconnues dans un dossier."""

    CERTIFICAT_SCOLARITE = "certificat_scolarite"
    CV = "cv"
    RELEVE_NOTES = "releve_notes"
    LETTRE_MOTIVATION = "lettre_motivation"
    ATTESTATION_NON_CUMUL = "attestation_non_cumul"
    LETTRE_RECOMMANDATION = "lettre_recommandation"
    JUSTIFICATIF_SOCIAL = "justificatif_social"
    JUSTIFICATIF_HANDICAP = "justificatif_handicap"
    AUTRE = "autre"


#: Pièces dont le contenu n'est jamais envoyé au LLM, ni stocké, ni indexé (RGPD).
PIECES_SENSIBLES = frozenset({TypePiece.JUSTIFICATIF_SOCIAL, TypePiece.JUSTIFICATIF_HANDICAP})


class MethodeExtraction(StrEnum):
    """Origine du texte d'une page."""

    TEXTE = "texte"
    OCR = "ocr"


class SourceMorceau(StrEnum):
    """Corpus d'origine d'un morceau indexé."""

    DOSSIER = "dossier"
    REGLEMENT = "reglement"


class Confiance(StrEnum):
    """Niveau de confiance d'une extraction."""

    HAUTE = "haute"
    MOYENNE = "moyenne"
    FAIBLE = "faible"
