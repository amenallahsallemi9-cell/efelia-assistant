"""Schémas Pydantic des sorties structurées du LLM (classification et lecture des pièces).

Chaque schéma sert à la fois de contrat envoyé au LLM (`response_format`) et de
validation de sa réponse. Les justificatifs sensibles n'ont PAS de schéma : ils ne
sont jamais lus.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.modeles import TypePiece

Extrait = Annotated[str, StringConstraints(max_length=300)]
Liste = Annotated[list[Annotated[str, StringConstraints(max_length=200)]], Field(max_length=30)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore")


# --------------------------------------------------------------------------- classification


class ClassementPage(_Strict):
    """Type de pièce d'une page."""

    numero: int = Field(description="Numéro de la page, tel que fourni.")
    type_piece: TypePiece
    confiance: float = Field(ge=0, le=1, description="Confiance entre 0 et 1.")
    indice: Annotated[str, StringConstraints(max_length=160)] = Field(
        description="Court indice textuel justifiant le classement."
    )


class ClassementPages(_Strict):
    """Classement d'un lot de pages."""

    pages: list[ClassementPage]


# --------------------------------------------------------------------------- lecture


class LectureCertificat(_Strict):
    """Certificat de scolarité."""

    nom: str | None = Field(description="Nom de famille de l'étudiant·e.")
    prenom: str | None = Field(description="Prénom(s) de l'étudiant·e.")
    etablissement: str | None = Field(description="Établissement qui délivre le certificat.")
    formation: str | None = Field(description="Formation suivie.")
    annee_universitaire: str | None = Field(description="Année universitaire, ex. 2026-2027.")
    extrait: Extrait | None = Field(
        description="Citation EXACTE du document prouvant l'inscription et l'année."
    )


class LectureCV(_Strict):
    """Curriculum vitae (le nombre de pages est compté sans le LLM)."""

    competences: Liste
    projets: Liste
    experiences: Liste
    liens: Liste = Field(description="Liens GitHub, portfolio, LinkedIn…")


class LectureReleve(_Strict):
    """Relevé de notes."""

    annee: str | None = Field(description="Année universitaire du relevé, ex. 2025-2026.")
    moyenne_generale: float | None = Field(ge=0, le=20, description="Moyenne générale sur 20.")
    mention: str | None
    credits_ects: int | None = Field(ge=0, le=300)
    extrait: Extrait | None = Field(description="Citation EXACTE indiquant l'année ou la moyenne.")


class ThemeLu(_Strict):
    """Présence d'un thème dans la lettre."""

    present: bool
    extrait: Extrait | None = Field(description="Citation EXACTE de la lettre, ou null.")


class LectureLettre(_Strict):
    """Lettre de motivation."""

    formation: ThemeLu = Field(description="La lettre parle-t-elle de la formation suivie ?")
    parcours: ThemeLu = Field(description="… du parcours antérieur ?")
    projet: ThemeLu = Field(description="… du projet (professionnel ou d'études) ?")
    mentionne_ia: bool = Field(
        description="La lettre mentionne-t-elle l'intelligence artificielle ?"
    )


class LectureAttestation(_Strict):
    """Attestation sur l'honneur de non-cumul."""

    mention_signature: bool = Field(
        description="Mention « Fait à … le … », « Signature » ou signature électronique présente."
    )
    lieu_date: str | None = Field(description="Texte « Fait à … le … » s'il existe.")
    bourse_declaree: str | None = Field(
        description="Bourse que la personne déclare percevoir, ou null si aucune."
    )
    extrait: Extrait | None = Field(description="Citation EXACTE de l'engagement sur l'honneur.")


class LectureRecommandation(_Strict):
    """Lettre de recommandation."""

    auteur: str | None
    fonction_auteur: str | None
    extrait: Extrait | None


SCHEMAS_LECTURE: dict[TypePiece, type[_Strict]] = {
    TypePiece.CERTIFICAT_SCOLARITE: LectureCertificat,
    TypePiece.CV: LectureCV,
    TypePiece.RELEVE_NOTES: LectureReleve,
    TypePiece.LETTRE_MOTIVATION: LectureLettre,
    TypePiece.ATTESTATION_NON_CUMUL: LectureAttestation,
    TypePiece.LETTRE_RECOMMANDATION: LectureRecommandation,
}
