"""Schémas de réponse de l'API (documentation OpenAPI et sérialisation)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.domain.modeles import Confiance, MethodeExtraction, StatutPipeline, TypePiece, Verdict


class _Sortie(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ReponseDepot(BaseModel):
    """Dossier reçu, traitement planifié."""

    id: uuid.UUID
    statut_pipeline: StatutPipeline
    nom_fichier_attendu: str
    message: str


class DossierResume(_Sortie):
    """Ligne du tableau de bord."""

    id: uuid.UUID
    nom: str
    prenom: str
    formation: str
    date_reception: datetime
    statut_pipeline: StatutPipeline
    verdict: Verdict | None = None
    garde_fou_declenche: bool = False
    created_at: datetime


class ListeDossiers(BaseModel):
    """Page de résultats."""

    elements: list[DossierResume]
    total: int
    page: int
    taille: int


class PageSortie(_Sortie):
    """Page du dossier (sans son texte)."""

    numero: int
    type_piece: TypePiece | None
    methode: MethodeExtraction
    confiance_classification: float | None
    sensible: bool


class PieceSortie(_Sortie):
    """Pièce et données extraites."""

    type: TypePiece
    pages: list[int]
    donnees_extraites: dict[str, Any]
    confiance: Confiance


class DecisionSortie(_Sortie):
    """Décision de recevabilité (le statut des règles fait foi)."""

    id: int
    statut_regles: Verdict
    statut_propose_llm: Verdict | None
    garde_fou_declenche: bool
    controles: list[dict[str, Any]]
    motifs: list[dict[str, Any]]
    avertissements: list[dict[str, Any]]
    conseils: list[dict[str, Any]]
    rapport: str
    modele: str
    created_at: datetime


class FicheSortie(_Sortie):
    """Informations déclarées."""

    nom: str
    prenom: str
    email: str
    formation: str
    inscrit_uca: bool
    heures_ia: int
    alternance: bool
    autre_bourse: bool
    autre_bourse_libelle: str | None
    date_reception: datetime
    nom_fichier: str


class DossierDetail(BaseModel):
    """Détail complet d'un dossier."""

    id: uuid.UUID
    statut_pipeline: StatutPipeline
    message_erreur: str | None
    nb_pages: int | None
    created_at: datetime
    nom_fichier_attendu: str
    fiche: FicheSortie
    pages: list[PageSortie]
    pieces: list[PieceSortie]
    decision: DecisionSortie | None
    nb_decisions: int


class TraceSortie(_Sortie):
    """Étape de la trace de l'agent."""

    ordre: int
    outil: str
    arguments: dict[str, Any]
    resultat: Any
    duree_ms: int
    tokens: int | None
    created_at: datetime


class ReponseInstruction(BaseModel):
    """Relance planifiée."""

    id: uuid.UUID
    message: str


class DemandeEligibilite(BaseModel):
    """Vérification rapide, sans dossier."""

    model_config = ConfigDict(extra="forbid")

    inscrit_uca: bool
    heures_ia: int = Field(ge=0, le=5000)
    alternance: bool
    autre_bourse: bool
    autre_bourse_libelle: str | None = Field(default=None, max_length=255)
    date_envoi: AwareDatetime | None = None


class ReponseEligibilite(BaseModel):
    """Résultat de la vérification rapide."""

    eligible: bool
    dans_les_delais: bool | None
    controles: list[dict[str, Any]]
    date_limite: datetime
    message: str


class PieceReglement(BaseModel):
    """Pièce listée par le règlement."""

    type: TypePiece
    libelle: str


class ResumeReglement(BaseModel):
    """Informations utiles à l'interface (compte à rebours, nom de fichier, pièces)."""

    edition: int
    annee_universitaire: str
    date_limite: datetime
    email_envoi: str
    prefixe_nom_fichier: str
    heures_ia_minimum: int
    cv_pages_max: int
    pieces_obligatoires: list[PieceReglement]
    pieces_facultatives: list[PieceReglement]
    laureats_max: int
    montant_euros: int


class Statistiques(BaseModel):
    """Compteurs du tableau de bord."""

    total: int
    par_verdict: dict[str, int]
    par_statut_pipeline: dict[str, int]
    pieces_manquantes: list[dict[str, Any]]
    garde_fous_declenches: int
