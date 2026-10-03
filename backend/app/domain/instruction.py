"""Instruction déterministe complète d'un dossier : tous les contrôles puis le statut."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.coherence import FaitsCoherence, verifier_coherence
from app.domain.modeles import Verdict
from app.domain.regles import (
    Controle,
    FaitsPieces,
    Fiche,
    Reglement,
    calculer_statut,
    verifier_eligibilite,
    verifier_format,
    verifier_pieces,
)


@dataclass(frozen=True)
class Instruction:
    """Résultat de l'instruction par les règles (fait foi, quel que soit l'avis du LLM)."""

    statut: Verdict
    controles: tuple[Controle, ...]

    @property
    def motifs(self) -> tuple[Controle, ...]:
        """Contrôles qui déterminent le statut (non conformes et non simples avertissements)."""
        return tuple(c for c in self.controles if c.effet is not None)

    @property
    def avertissements(self) -> tuple[Controle, ...]:
        """Points à signaler sans effet sur le statut."""
        return tuple(c for c in self.controles if c.est_avertissement)


def instruire(
    fiche: Fiche,
    nom_fichier: str,
    date_reception: datetime,
    pieces: FaitsPieces,
    coherence: FaitsCoherence,
    reglement: Reglement,
) -> Instruction:
    """Applique toutes les règles du règlement et calcule le statut de recevabilité."""
    controles = (
        *verifier_eligibilite(fiche, reglement),
        *verifier_format(nom_fichier, date_reception, fiche, reglement),
        *verifier_pieces(pieces, reglement),
        *verifier_coherence(fiche, coherence, reglement),
    )
    return Instruction(statut=calculer_statut(controles), controles=controles)
