"""Vérification rapide d'éligibilité et résumé du règlement (sans dossier)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependances import limiter_eligibilite
from app.api.schemas import DemandeEligibilite, PieceReglement, ReponseEligibilite, ResumeReglement
from app.core.reglement import get_reglement
from app.domain.modeles import Verdict
from app.domain.regles import (
    Fiche,
    Reglement,
    Resultat,
    calculer_statut,
    verifier_delai,
    verifier_eligibilite,
)
from app.services.agent.contexte import controle_vers_dict

routeur = APIRouter(tags=["règlement"])
ReglementDep = Annotated[Reglement, Depends(get_reglement)]


@routeur.post(
    "/eligibilite",
    response_model=ReponseEligibilite,
    summary="Vérification rapide",
    dependencies=[Depends(limiter_eligibilite)],
)
def eligibilite(demande: DemandeEligibilite, reglement: ReglementDep) -> ReponseEligibilite:
    """Les 4 conditions d'éligibilité et, si une date est fournie, le respect du délai."""
    fiche = Fiche(
        nom="-",
        prenom="-",
        inscrit_uca=demande.inscrit_uca,
        heures_ia=demande.heures_ia,
        alternance=demande.alternance,
        autre_bourse=demande.autre_bourse,
        autre_bourse_libelle=demande.autre_bourse_libelle,
    )
    controles = verifier_eligibilite(fiche, reglement)
    delai = verifier_delai(demande.date_envoi or datetime.now(UTC), reglement)
    eligible = calculer_statut(controles) is Verdict.RECEVABLE
    dans_les_delais = delai.resultat is Resultat.CONFORME
    if not eligible:
        message = "Au moins une condition d'éligibilité n'est pas remplie."
    elif not dans_les_delais:
        message = "Conditions remplies, mais la date limite est dépassée."
    else:
        message = "Les conditions d'éligibilité sont remplies : vous pouvez préparer votre dossier."
    return ReponseEligibilite(
        eligible=eligible,
        dans_les_delais=dans_les_delais,
        controles=[controle_vers_dict(c) for c in (*controles, delai)],
        date_limite=reglement.reception_avant,
        message=message,
    )


@routeur.get("/reglement", response_model=ResumeReglement, summary="Résumé du règlement")
def resume_reglement(reglement: ReglementDep) -> ResumeReglement:
    """Date limite, pièces, nom de fichier attendu : de quoi guider le dépôt."""
    return ResumeReglement(
        edition=reglement.edition,
        annee_universitaire=reglement.annee_universitaire,
        date_limite=reglement.reception_avant,
        email_envoi=reglement.email_envoi,
        prefixe_nom_fichier=reglement.prefixe_nom_fichier,
        heures_ia_minimum=reglement.heures_ia_minimum,
        cv_pages_max=reglement.cv_pages_max,
        pieces_obligatoires=[
            PieceReglement(type=p.type, libelle=p.libelle) for p in reglement.pieces_obligatoires
        ],
        pieces_facultatives=[
            PieceReglement(type=p.type, libelle=p.libelle) for p in reglement.pieces_facultatives
        ],
        laureats_max=reglement.selection.laureats_max,
        montant_euros=reglement.selection.montant_euros,
    )
