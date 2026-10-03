"""Chargement et validation du règlement versionné (`config/regles_AAAA.yaml`)."""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import get_parametres
from app.domain.modeles import TypePiece
from app.domain.regles import (
    BourseCompatible,
    Consequence,
    PieceRequise,
    Reglement,
    Selection,
)

#: Codes de contrôle dont la conséquence doit obligatoirement être configurée.
CODES_CONTROLES = frozenset(
    {
        "eligibilite_inscription_uca",
        "eligibilite_heures_ia",
        "eligibilite_alternance",
        "eligibilite_autre_bourse",
        "format_delai",
        "format_nom_fichier",
        "piece_manquante",
        "cv_nombre_pages",
        "attestation_signature",
        "certificat_annee",
        "certificat_etablissement",
        "certificat_identite",
        "lettre_themes",
        "releve_annee",
        "attestation_bourse_declaree",
    }
)


class ErreurReglement(ValueError):
    """Fichier de règlement absent ou invalide."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Etablissement(_Strict):
    nom: str
    alias: list[str] = []


class _Bourse(_Strict):
    libelle: str
    mots_cles: list[list[str]] = Field(min_length=1)


class _Eligibilite(_Strict):
    inscription_uca_requise: bool
    heures_ia_minimum: int = Field(ge=0)
    alternance_autorisee: bool
    bourses_compatibles: list[_Bourse] = []


class _Format(_Strict):
    prefixe_nom_fichier: str
    email_envoi: str
    reception_avant: datetime
    fuseau: str

    @model_validator(mode="after")
    def _date_locale(self) -> "_Format":
        if self.reception_avant.tzinfo is not None:
            raise ValueError("reception_avant doit être une heure locale : le fuseau est à part.")
        try:
            ZoneInfo(self.fuseau)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Fuseau horaire inconnu : {self.fuseau}") from exc
        return self


class _Piece(_Strict):
    type: TypePiece
    libelle: str


class _Contraintes(_Strict):
    cv_pages_max: int = Field(gt=0)
    lettre_themes: list[str] = Field(min_length=1)
    annee_releve_attendue: str


class _Selection(_Strict):
    criteres: list[str]
    laureats_max: int
    montant_euros: int
    versement: str
    reconduction_automatique: bool


class _FichierReglement(_Strict):
    edition: int
    annee_universitaire: str = Field(pattern=r"^\d{4}-\d{4}$")
    etablissement: _Etablissement
    eligibilite: _Eligibilite
    format: _Format
    pieces_obligatoires: list[_Piece] = Field(min_length=1)
    pieces_facultatives: list[_Piece] = []
    contraintes: _Contraintes
    consequences: dict[str, Consequence]
    selection: _Selection

    @field_validator("consequences")
    @classmethod
    def _codes_complets(cls, valeur: dict[str, Consequence]) -> dict[str, Consequence]:
        manquants = CODES_CONTROLES - valeur.keys()
        inconnus = valeur.keys() - CODES_CONTROLES
        if manquants:
            raise ValueError(f"Conséquences manquantes : {', '.join(sorted(manquants))}")
        if inconnus:
            raise ValueError(f"Codes de contrôle inconnus : {', '.join(sorted(inconnus))}")
        return valeur

    def vers_domaine(self) -> Reglement:
        """Convertit le fichier validé en objet métier."""
        return Reglement(
            edition=self.edition,
            annee_universitaire=self.annee_universitaire,
            etablissement=self.etablissement.nom,
            etablissement_alias=tuple(self.etablissement.alias),
            inscription_uca_requise=self.eligibilite.inscription_uca_requise,
            heures_ia_minimum=self.eligibilite.heures_ia_minimum,
            alternance_autorisee=self.eligibilite.alternance_autorisee,
            bourses_compatibles=tuple(
                BourseCompatible(b.libelle, tuple(tuple(g) for g in b.mots_cles))
                for b in self.eligibilite.bourses_compatibles
            ),
            prefixe_nom_fichier=self.format.prefixe_nom_fichier,
            email_envoi=self.format.email_envoi,
            reception_avant=self.format.reception_avant.replace(
                tzinfo=ZoneInfo(self.format.fuseau)
            ),
            pieces_obligatoires=tuple(
                PieceRequise(p.type, p.libelle) for p in self.pieces_obligatoires
            ),
            pieces_facultatives=tuple(
                PieceRequise(p.type, p.libelle) for p in self.pieces_facultatives
            ),
            cv_pages_max=self.contraintes.cv_pages_max,
            lettre_themes=tuple(self.contraintes.lettre_themes),
            annee_releve_attendue=self.contraintes.annee_releve_attendue,
            consequences=dict(self.consequences),
            selection=Selection(
                criteres=tuple(self.selection.criteres),
                laureats_max=self.selection.laureats_max,
                montant_euros=self.selection.montant_euros,
                versement=self.selection.versement,
                reconduction_automatique=self.selection.reconduction_automatique,
            ),
        )


def charger_reglement(chemin: Path) -> Reglement:
    """Lit, valide et convertit un fichier de règlement YAML."""
    try:
        contenu = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ErreurReglement(f"Fichier de règlement introuvable : {chemin}") from exc
    except yaml.YAMLError as exc:
        raise ErreurReglement(f"YAML invalide dans {chemin} : {exc}") from exc
    try:
        return _FichierReglement.model_validate(contenu).vers_domaine()
    except ValueError as exc:
        raise ErreurReglement(f"Règlement invalide ({chemin}) : {exc}") from exc


@lru_cache
def get_reglement() -> Reglement:
    """Règlement de l'édition configurée (`REGLES_FICHIER`), chargé une seule fois."""
    return charger_reglement(get_parametres().regles_fichier)
