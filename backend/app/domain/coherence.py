"""Contrôles de cohérence déterministes entre la fiche et les données lues dans les pièces.

Une donnée absente (`None`) donne un résultat INDETERMINE (avertissement, vérification
humaine) ; une pièce absente ne produit aucun contrôle ici (déjà signalée comme manquante).
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.domain.noms import identite_correspond, jetons
from app.domain.regles import (
    Categorie,
    Controle,
    Fiche,
    Preuve,
    Reglement,
    Resultat,
    bourse_est_compatible,
)

_ANNEE = re.compile(r"(20\d{2})\s*[-/–—]\s*(20\d{2}|\d{2})(?!\d)")


@dataclass(frozen=True)
class DonneesCertificat:
    """Informations lues sur le certificat de scolarité."""

    nom: str | None = None
    prenom: str | None = None
    etablissement: str | None = None
    annee_universitaire: str | None = None
    page: int | None = None
    extrait: str | None = None


@dataclass(frozen=True)
class ThemeLettre:
    """Présence d'un thème exigé dans la lettre, avec un extrait justificatif."""

    present: bool
    extrait: str | None = None
    page: int | None = None


@dataclass(frozen=True)
class DonneesLettre:
    """Thèmes détectés dans la lettre de motivation."""

    themes: Mapping[str, ThemeLettre] = field(default_factory=dict)
    page: int | None = None


@dataclass(frozen=True)
class DonneesReleve:
    """Informations lues sur les relevés de notes."""

    annee: str | None = None
    page: int | None = None


@dataclass(frozen=True)
class DonneesAttestation:
    """Bourse éventuellement mentionnée dans l'attestation de non-cumul."""

    bourse_declaree: str | None = None
    page: int | None = None
    extrait: str | None = None


@dataclass(frozen=True)
class FaitsCoherence:
    """Données lues dans les pièces (None si la pièce est absente)."""

    certificat: DonneesCertificat | None = None
    lettre: DonneesLettre | None = None
    releve: DonneesReleve | None = None
    attestation: DonneesAttestation | None = None


def normaliser_annee(texte: str | None) -> str | None:
    """Année universitaire canonique (« 2026/27 » → « 2026-2027 »), None si introuvable."""
    if not texte:
        return None
    correspondance = _ANNEE.search(texte)
    if not correspondance:
        return None
    debut, fin = correspondance.groups()
    if len(fin) == 2:
        fin = debut[:2] + fin
    return f"{debut}-{fin}"


def etablissement_reconnu(etablissement: str, reglement: Reglement) -> bool:
    """Vrai si l'établissement correspond au nom officiel ou à un alias (suite de mots)."""
    mots = jetons(etablissement)
    for alias in (reglement.etablissement, *reglement.etablissement_alias):
        cible = jetons(alias)
        n = len(cible)
        if n and any(mots[i : i + n] == cible for i in range(len(mots) - n + 1)):
            return True
    return False


def _controle(
    code: str,
    libelle: str,
    resultat: Resultat,
    message: str,
    reglement: Reglement,
    preuves: tuple[Preuve, ...],
) -> Controle:
    return Controle(
        code=code,
        categorie=Categorie.COHERENCE,
        libelle=libelle,
        resultat=resultat,
        consequence=reglement.consequence(code),
        message=message,
        preuves=preuves,
    )


def _controles_certificat(
    certificat: DonneesCertificat, fiche: Fiche, reglement: Reglement
) -> list[Controle]:
    preuves = (Preuve(source="document", page=certificat.page, extrait=certificat.extrait),)
    controles = []

    if not certificat.nom or not certificat.prenom:
        resultat, message = Resultat.INDETERMINE, "Identité illisible sur le certificat."
    elif identite_correspond(fiche.nom, fiche.prenom, certificat.nom, certificat.prenom):
        resultat, message = Resultat.CONFORME, "L'identité du certificat correspond à la fiche."
    else:
        resultat = Resultat.NON_CONFORME
        message = (
            f"Le certificat est au nom de « {certificat.prenom} {certificat.nom} », "
            f"la fiche indique « {fiche.prenom} {fiche.nom} »."
        )
    controles.append(
        _controle(
            "certificat_identite", "Identité du certificat", resultat, message, reglement, preuves
        )
    )

    annee = normaliser_annee(certificat.annee_universitaire)
    attendue = reglement.annee_universitaire
    if annee is None:
        resultat, message = Resultat.INDETERMINE, "Année universitaire illisible sur le certificat."
    elif annee == attendue:
        resultat, message = Resultat.CONFORME, f"Certificat de l'année {attendue}."
    else:
        resultat = Resultat.NON_CONFORME
        message = f"Le certificat porte sur l'année {annee}, et non sur l'année {attendue}."
    controles.append(
        _controle(
            "certificat_annee",
            f"Certificat de l'année {attendue}",
            resultat,
            message,
            reglement,
            preuves,
        )
    )

    if not certificat.etablissement:
        resultat, message = Resultat.INDETERMINE, "Établissement illisible sur le certificat."
    elif etablissement_reconnu(certificat.etablissement, reglement):
        resultat, message = Resultat.CONFORME, f"Certificat délivré par {reglement.etablissement}."
    else:
        resultat = Resultat.NON_CONFORME
        message = (
            f"Le certificat est délivré par « {certificat.etablissement} », "
            f"et non par {reglement.etablissement}."
        )
    controles.append(
        _controle(
            "certificat_etablissement",
            f"Certificat délivré par {reglement.etablissement}",
            resultat,
            message,
            reglement,
            preuves,
        )
    )
    return controles


def _controle_lettre(lettre: DonneesLettre, reglement: Reglement) -> Controle:
    attendus = ", ".join(reglement.lettre_themes)
    if not lettre.themes:
        return _controle(
            "lettre_themes",
            f"Lettre de motivation : {attendus}",
            Resultat.INDETERMINE,
            "Thèmes de la lettre non déterminés : relecture humaine conseillée.",
            reglement,
            (Preuve(source="document", page=lettre.page),),
        )
    manquants = [
        t
        for t in reglement.lettre_themes
        if not (lettre.themes.get(t) and lettre.themes[t].present)
    ]
    preuves = tuple(
        Preuve(source="document", page=theme.page or lettre.page, extrait=theme.extrait)
        for nom, theme in lettre.themes.items()
        if theme.present and nom in reglement.lettre_themes
    ) or (Preuve(source="document", page=lettre.page),)
    if not manquants:
        resultat, message = Resultat.CONFORME, f"La lettre aborde bien : {attendus}."
    else:
        resultat = Resultat.NON_CONFORME
        message = (
            f"La lettre ne semble pas aborder : {', '.join(manquants)} (attendu : {attendus})."
        )
    return _controle(
        "lettre_themes",
        f"Lettre de motivation : {attendus}",
        resultat,
        message,
        reglement,
        preuves,
    )


def _controle_releve(releve: DonneesReleve, reglement: Reglement) -> Controle:
    annee = normaliser_annee(releve.annee)
    attendue = reglement.annee_releve_attendue
    if annee is None:
        resultat, message = Resultat.INDETERMINE, "Année des relevés de notes non déterminée."
    elif annee == attendue:
        resultat, message = Resultat.CONFORME, f"Relevés de notes de l'année {attendue}."
    else:
        resultat = Resultat.NON_CONFORME
        message = (
            f"Les relevés portent sur l'année {annee} : la dernière année d'études "
            f"attendue est {attendue}."
        )
    return _controle(
        "releve_annee",
        "Relevés de la dernière année d'études",
        resultat,
        message,
        reglement,
        (Preuve(source="document", page=releve.page, extrait=releve.annee),),
    )


def _controle_attestation(
    attestation: DonneesAttestation, fiche: Fiche, reglement: Reglement
) -> Controle:
    bourse = attestation.bourse_declaree
    incompatible = bool(bourse) and not bourse_est_compatible(bourse, reglement)
    if not incompatible:
        resultat = Resultat.CONFORME
        message = "L'attestation ne mentionne aucune bourse incompatible."
    else:
        resultat = Resultat.NON_CONFORME
        message = f"L'attestation mentionne une bourse (« {bourse} ») non cumulable" + (
            ", alors que la fiche n'en déclare aucune." if not fiche.autre_bourse else "."
        )
    return _controle(
        "attestation_bourse_declaree",
        "Bourse mentionnée dans l'attestation",
        resultat,
        message,
        reglement,
        (Preuve(source="document", page=attestation.page, extrait=attestation.extrait),),
    )


def verifier_coherence(fiche: Fiche, faits: FaitsCoherence, reglement: Reglement) -> list[Controle]:
    """Contrôles croisés fiche ↔ documents (identité, année, établissement, lettre…)."""
    controles: list[Controle] = []
    if faits.certificat is not None:
        controles += _controles_certificat(faits.certificat, fiche, reglement)
    if faits.lettre is not None:
        controles.append(_controle_lettre(faits.lettre, reglement))
    if faits.releve is not None:
        controles.append(_controle_releve(faits.releve, reglement))
    if faits.attestation is not None:
        controles.append(_controle_attestation(faits.attestation, fiche, reglement))
    return controles
