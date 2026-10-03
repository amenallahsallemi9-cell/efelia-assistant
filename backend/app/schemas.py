"""Schémas Pydantic partagés entre l'API et les services."""

from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.domain.regles import Fiche

TexteCourt = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class FicheDeclaree(BaseModel):
    """Informations déclarées par l'étudiant·e lors du dépôt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nom: TexteCourt
    prenom: TexteCourt
    email: Annotated[str, StringConstraints(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    formation: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    inscrit_uca: bool
    heures_ia: int = Field(ge=0, le=5000)
    alternance: bool
    autre_bourse: bool
    autre_bourse_libelle: Annotated[str, StringConstraints(max_length=255)] | None = None
    date_envoi: AwareDatetime | None = Field(
        default=None,
        description="Date d'envoi du dossier par email. À défaut, la date du dépôt fait foi.",
    )

    def vers_domaine(self) -> Fiche:
        """Convertit en fiche du domaine (règles pures)."""
        return Fiche(
            nom=self.nom,
            prenom=self.prenom,
            inscrit_uca=self.inscrit_uca,
            heures_ia=self.heures_ia,
            alternance=self.alternance,
            autre_bourse=self.autre_bourse,
            autre_bourse_libelle=self.autre_bourse_libelle or None,
            formation=self.formation,
        )


def date_reception(fiche: FicheDeclaree, maintenant: datetime) -> datetime:
    """Date de réception retenue : date d'envoi déclarée, sinon horodatage du dépôt."""
    return fiche.date_envoi or maintenant
