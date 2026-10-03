"""État partagé par les outils pendant une instruction."""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.db.modeles import Dossier
from app.domain.coherence import FaitsCoherence
from app.domain.instruction import Instruction, instruire
from app.domain.modeles import Verdict
from app.domain.regles import Controle, FaitsPieces, Fiche, Reglement
from app.providers import Fournisseurs
from app.services.faits import construire_faits


@dataclass(frozen=True)
class PropositionDecision:
    """Décision proposée par le LLM via `enregistrer_decision` (jamais appliquée telle quelle)."""

    statut: Verdict
    motifs: list[dict[str, Any]]
    conseils: list[dict[str, Any]]


@dataclass
class ContexteAgent:
    """Dossier en cours, règlement, fournisseurs et proposition éventuelle du LLM."""

    session: Session
    dossier: Dossier
    reglement: Reglement
    fournisseurs: Fournisseurs
    proposition: PropositionDecision | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def fiche(self) -> Fiche:
        """Fiche déclarative au format du domaine."""
        return fiche_du_dossier(self.dossier)

    def faits(self) -> tuple[FaitsPieces, FaitsCoherence]:
        """Faits établis à partir des pièces lues."""
        return construire_faits(self.dossier.pieces)

    def instruction(self) -> Instruction:
        """Instruction complète par les règles : elle fait foi (garde-fou)."""
        return instruire_par_regles(self.dossier, self.reglement)


def fiche_du_dossier(dossier: Dossier) -> Fiche:
    """Fiche du domaine reconstruite depuis la base."""
    return Fiche(
        nom=dossier.nom,
        prenom=dossier.prenom,
        inscrit_uca=dossier.inscrit_uca,
        heures_ia=dossier.heures_ia,
        alternance=dossier.alternance,
        autre_bourse=dossier.autre_bourse,
        autre_bourse_libelle=dossier.autre_bourse_libelle,
        formation=dossier.formation,
    )


def instruire_par_regles(dossier: Dossier, reglement: Reglement) -> Instruction:
    """Applique toutes les règles du domaine au dossier."""
    faits_pieces, faits_coherence = construire_faits(dossier.pieces)
    return instruire(
        fiche_du_dossier(dossier),
        dossier.nom_fichier,
        dossier.date_reception,
        faits_pieces,
        faits_coherence,
        reglement,
    )


def controle_vers_dict(controle: Controle) -> dict[str, Any]:
    """Représentation JSON d'un contrôle (outils, base, API)."""
    return {
        "code": controle.code,
        "categorie": controle.categorie.value,
        "libelle": controle.libelle,
        "resultat": controle.resultat.value,
        "consequence": controle.consequence.value,
        "message": controle.message,
        "preuves": [
            {"source": p.source, "page": p.page, "extrait": p.extrait} for p in controle.preuves
        ],
    }
