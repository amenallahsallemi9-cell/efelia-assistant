"""Règles de recevabilité : fonctions pures, sans dépendance externe.

Le statut final d'un dossier est TOUJOURS calculé ici (`calculer_statut`), jamais par le
LLM : c'est le garde-fou central de l'application. Chaque contrôle produit un `Controle`
avec son résultat, sa conséquence (tirée du règlement) et ses preuves.

Un résultat INDETERMINE (information illisible, absente des documents) ne change jamais
le statut : il produit un avertissement invitant à une vérification humaine.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.modeles import TypePiece, Verdict
from app.domain.noms import nom_fichier_attendu, nom_fichier_conforme, normaliser

# --------------------------------------------------------------------------- vocabulaire


class Consequence(StrEnum):
    """Effet d'un contrôle non conforme sur le statut du dossier."""

    NON_RECEVABLE = "NON_RECEVABLE"
    A_COMPLETER = "A_COMPLETER"
    AVERTISSEMENT = "AVERTISSEMENT"


class Resultat(StrEnum):
    """Résultat d'un contrôle (✅ conforme, ❌ non conforme, ⚠️ indéterminé, ➖ sans objet)."""

    CONFORME = "CONFORME"
    NON_CONFORME = "NON_CONFORME"
    INDETERMINE = "INDETERMINE"
    NON_APPLICABLE = "NON_APPLICABLE"


class Categorie(StrEnum):
    """Famille de contrôle (regroupement dans l'interface)."""

    ELIGIBILITE = "eligibilite"
    FORMAT = "format"
    PIECES = "pieces"
    COHERENCE = "coherence"


@dataclass(frozen=True)
class Preuve:
    """Élément justifiant un contrôle : page du dossier et extrait, ou champ de la fiche."""

    source: str  # "fiche" | "document" | "fichier"
    page: int | None = None
    extrait: str | None = None


@dataclass(frozen=True)
class Controle:
    """Résultat d'une règle appliquée au dossier."""

    code: str
    categorie: Categorie
    libelle: str
    resultat: Resultat
    consequence: Consequence
    message: str
    preuves: tuple[Preuve, ...] = ()

    @property
    def effet(self) -> Consequence | None:
        """Conséquence effective sur le statut (None si le contrôle ne pèse pas)."""
        if self.resultat is Resultat.NON_CONFORME and self.consequence is not (
            Consequence.AVERTISSEMENT
        ):
            return self.consequence
        return None

    @property
    def est_avertissement(self) -> bool:
        """Vrai si le contrôle doit être signalé sans changer le statut."""
        return self.resultat is Resultat.INDETERMINE or (
            self.resultat is Resultat.NON_CONFORME and self.consequence is Consequence.AVERTISSEMENT
        )


# --------------------------------------------------------------------------- règlement


@dataclass(frozen=True)
class BourseCompatible:
    """Bourse cumulable, reconnue par groupes de mots-clés (tous les mots d'un groupe)."""

    libelle: str
    mots_cles: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class PieceRequise:
    """Pièce listée par le règlement."""

    type: TypePiece
    libelle: str


@dataclass(frozen=True)
class Selection:
    """Modalités de sélection : informatives, pour les conseils uniquement."""

    criteres: tuple[str, ...]
    laureats_max: int
    montant_euros: int
    versement: str
    reconduction_automatique: bool


@dataclass(frozen=True)
class Reglement:
    """Règlement d'une édition, chargé depuis le YAML versionné."""

    edition: int
    annee_universitaire: str
    etablissement: str
    etablissement_alias: tuple[str, ...]
    inscription_uca_requise: bool
    heures_ia_minimum: int
    alternance_autorisee: bool
    bourses_compatibles: tuple[BourseCompatible, ...]
    prefixe_nom_fichier: str
    email_envoi: str
    reception_avant: datetime  # borne exclusive, avec fuseau horaire
    pieces_obligatoires: tuple[PieceRequise, ...]
    pieces_facultatives: tuple[PieceRequise, ...]
    cv_pages_max: int
    lettre_themes: tuple[str, ...]
    annee_releve_attendue: str
    consequences: Mapping[str, Consequence]
    selection: Selection

    def __post_init__(self) -> None:
        if self.reception_avant.tzinfo is None:
            raise ValueError("La date limite doit comporter un fuseau horaire.")

    def consequence(self, code: str) -> Consequence:
        """Conséquence configurée pour un code de contrôle."""
        try:
            return self.consequences[code]
        except KeyError as exc:
            raise KeyError(f"Conséquence non configurée pour le contrôle « {code} ».") from exc

    def libelle_piece(self, type_piece: TypePiece) -> str:
        """Libellé réglementaire d'une pièce."""
        for piece in (*self.pieces_obligatoires, *self.pieces_facultatives):
            if piece.type is type_piece:
                return piece.libelle
        return type_piece.value


# --------------------------------------------------------------------------- entrées


@dataclass(frozen=True)
class Fiche:
    """Informations déclarées par l'étudiant·e."""

    nom: str
    prenom: str
    inscrit_uca: bool
    heures_ia: int
    alternance: bool
    autre_bourse: bool
    autre_bourse_libelle: str | None = None
    formation: str = ""

    def __post_init__(self) -> None:
        if self.heures_ia < 0:
            raise ValueError("Le nombre d'heures d'IA ne peut pas être négatif.")


@dataclass(frozen=True)
class FaitsPieces:
    """Faits établis à partir des pièces du dossier (classification + lecture).

    Les valeurs `None` signifient « non déterminé » (non lu, illisible…).
    """

    pages: Mapping[TypePiece, tuple[int, ...]] = field(default_factory=dict)
    cv_nb_pages: int | None = None
    attestation_signee: bool | None = None
    attestation_extrait: str | None = None

    def presente(self, type_piece: TypePiece) -> bool:
        """Vrai si au moins une page a été classée dans ce type de pièce."""
        return bool(self.pages.get(type_piece))

    def premiere_page(self, type_piece: TypePiece) -> int | None:
        """Première page de la pièce, pour citer une preuve."""
        pages = self.pages.get(type_piece)
        return min(pages) if pages else None


# --------------------------------------------------------------------------- éligibilité


def bourse_est_compatible(libelle: str | None, reglement: Reglement) -> bool:
    """Vrai si le libellé désigne une bourse cumulable (ex. CROUS sur critères sociaux)."""
    if not libelle:
        return False
    mots = normaliser(libelle)
    return any(
        all(mot in mots for mot in groupe)
        for bourse in reglement.bourses_compatibles
        for groupe in bourse.mots_cles
    )


def verifier_eligibilite(fiche: Fiche, reglement: Reglement) -> list[Controle]:
    """Les 4 conditions d'éligibilité, d'après la fiche déclarative."""

    def _controle(code: str, libelle: str, ok: bool, message: str, champ: str) -> Controle:
        return Controle(
            code=code,
            categorie=Categorie.ELIGIBILITE,
            libelle=libelle,
            resultat=Resultat.CONFORME if ok else Resultat.NON_CONFORME,
            consequence=reglement.consequence(code),
            message=message,
            preuves=(Preuve(source="fiche", extrait=champ),),
        )

    controles = []

    inscrit_ok = fiche.inscrit_uca or not reglement.inscription_uca_requise
    controles.append(
        _controle(
            "eligibilite_inscription_uca",
            f"Inscription à {reglement.etablissement}",
            inscrit_ok,
            f"Inscription à {reglement.etablissement} déclarée."
            if inscrit_ok
            else f"La bourse est réservée aux personnes inscrites à {reglement.etablissement}.",
            f"Inscrit·e à UCA : {'oui' if fiche.inscrit_uca else 'non'}",
        )
    )

    heures_ok = fiche.heures_ia >= reglement.heures_ia_minimum
    controles.append(
        _controle(
            "eligibilite_heures_ia",
            f"Formation avec au moins {reglement.heures_ia_minimum} h d'enseignement en IA",
            heures_ok,
            f"{fiche.heures_ia} h d'IA déclarées (minimum {reglement.heures_ia_minimum} h)."
            if heures_ok
            else (
                f"{fiche.heures_ia} h d'IA déclarées : il en faut au moins "
                f"{reglement.heures_ia_minimum}."
            ),
            f"Heures d'IA : {fiche.heures_ia}",
        )
    )

    alternance_ok = reglement.alternance_autorisee or not fiche.alternance
    controles.append(
        _controle(
            "eligibilite_alternance",
            "Formation hors alternance",
            alternance_ok,
            "Formation suivie hors alternance."
            if alternance_ok
            else "Les formations en alternance ne sont pas éligibles.",
            f"Alternance : {'oui' if fiche.alternance else 'non'}",
        )
    )

    compatible = fiche.autre_bourse and bourse_est_compatible(fiche.autre_bourse_libelle, reglement)
    bourse_ok = not fiche.autre_bourse or compatible
    if not fiche.autre_bourse:
        message = "Aucune autre bourse d'études déclarée."
    elif compatible:
        message = (
            f"Bourse déclarée (« {fiche.autre_bourse_libelle} ») compatible : "
            "la bourse CROUS sur critères sociaux est cumulable."
        )
    else:
        message = (
            "Une autre bourse d'études est déclarée pour la même année universitaire"
            + (f" (« {fiche.autre_bourse_libelle} »)" if fiche.autre_bourse_libelle else "")
            + " : seule la bourse CROUS sur critères sociaux est cumulable. "
            "S'il s'agit d'une aide ponctuelle ou de mobilité, vérifiez auprès d'EFELIA "
            f"({reglement.email_envoi})."
        )
    controles.append(
        _controle(
            "eligibilite_autre_bourse",
            "Pas d'autre bourse d'études (hors CROUS sur critères sociaux)",
            bourse_ok,
            message,
            "Autre bourse : "
            + ((fiche.autre_bourse_libelle or "oui") if fiche.autre_bourse else "non"),
        )
    )
    return controles


# --------------------------------------------------------------------------- format


def verifier_delai(date_reception: datetime, reglement: Reglement) -> Controle:
    """Le dossier doit être reçu strictement avant la borne (fin du 18/10/2026, Paris)."""
    if date_reception.tzinfo is None:
        raise ValueError("La date de réception doit comporter un fuseau horaire.")
    dans_les_temps = date_reception < reglement.reception_avant
    fuseau = reglement.reception_avant.tzinfo
    recu = date_reception.astimezone(fuseau).strftime("%d/%m/%Y à %H:%M:%S")
    return Controle(
        code="format_delai",
        categorie=Categorie.FORMAT,
        libelle="Réception avant la date limite",
        resultat=Resultat.CONFORME if dans_les_temps else Resultat.NON_CONFORME,
        consequence=reglement.consequence("format_delai"),
        message=(
            f"Dossier reçu le {recu} (heure de Paris), dans les délais."
            if dans_les_temps
            else f"Dossier reçu le {recu} (heure de Paris), après la date limite."
        ),
        preuves=(Preuve(source="fiche", extrait=f"Date de réception : {recu}"),),
    )


def verifier_nom_fichier(nom_fichier: str, fiche: Fiche, reglement: Reglement) -> Controle:
    """Le fichier doit s'appeler `BourseExcellence2026_NOM.PRENOM` (casse et accents ignorés)."""
    attendu = nom_fichier_attendu(reglement.prefixe_nom_fichier, fiche.nom, fiche.prenom)
    ok = nom_fichier_conforme(nom_fichier, reglement.prefixe_nom_fichier, fiche.nom, fiche.prenom)
    return Controle(
        code="format_nom_fichier",
        categorie=Categorie.FORMAT,
        libelle="Nom du fichier",
        resultat=Resultat.CONFORME if ok else Resultat.NON_CONFORME,
        consequence=reglement.consequence("format_nom_fichier"),
        message=(
            "Nom de fichier conforme."
            if ok
            else f"Nom de fichier « {nom_fichier} » non conforme : attendu « {attendu} »."
        ),
        preuves=(Preuve(source="fichier", extrait=nom_fichier),),
    )


def verifier_format(
    nom_fichier: str, date_reception: datetime, fiche: Fiche, reglement: Reglement
) -> list[Controle]:
    """Contrôles de format : nom du fichier et date de réception."""
    return [
        verifier_nom_fichier(nom_fichier, fiche, reglement),
        verifier_delai(date_reception, reglement),
    ]


# --------------------------------------------------------------------------- pièces


def verifier_pieces(faits: FaitsPieces, reglement: Reglement) -> list[Controle]:
    """Présence des pièces obligatoires et facultatives, longueur du CV, signature."""
    controles: list[Controle] = []

    for piece in reglement.pieces_obligatoires:
        presente = faits.presente(piece.type)
        pages = faits.pages.get(piece.type, ())
        controles.append(
            Controle(
                code=f"piece_{piece.type.value}",
                categorie=Categorie.PIECES,
                libelle=piece.libelle,
                resultat=Resultat.CONFORME if presente else Resultat.NON_CONFORME,
                consequence=reglement.consequence("piece_manquante"),
                message=(
                    f"Pièce présente ({_pages_texte(pages)})."
                    if presente
                    else f"Pièce obligatoire manquante : {piece.libelle}."
                ),
                preuves=tuple(Preuve(source="document", page=p) for p in pages[:1]),
            )
        )

    for piece in reglement.pieces_facultatives:
        pages = faits.pages.get(piece.type, ())
        controles.append(
            Controle(
                code=f"piece_{piece.type.value}",
                categorie=Categorie.PIECES,
                libelle=piece.libelle,
                resultat=Resultat.CONFORME if pages else Resultat.NON_APPLICABLE,
                consequence=Consequence.AVERTISSEMENT,
                message=(
                    f"Pièce facultative fournie ({_pages_texte(pages)})."
                    if pages
                    else "Pièce facultative non fournie."
                ),
                preuves=tuple(Preuve(source="document", page=p) for p in pages[:1]),
            )
        )

    if faits.presente(TypePiece.CV):
        controles.append(_controle_cv(faits, reglement))
    if faits.presente(TypePiece.ATTESTATION_NON_CUMUL):
        controles.append(_controle_signature(faits, reglement))
    return controles


def _pages_texte(pages: Iterable[int]) -> str:
    liste = sorted(pages)
    return ("page " if len(liste) == 1 else "pages ") + ", ".join(map(str, liste))


def _controle_cv(faits: FaitsPieces, reglement: Reglement) -> Controle:
    maximum = reglement.cv_pages_max
    nb = faits.cv_nb_pages
    if nb is None:
        resultat, message = Resultat.INDETERMINE, "Nombre de pages du CV non déterminé."
    elif nb <= maximum:
        resultat, message = Resultat.CONFORME, f"CV de {nb} page(s) (maximum {maximum})."
    else:
        resultat = Resultat.NON_CONFORME
        message = f"CV de {nb} pages : le règlement impose {maximum} pages maximum."
    return Controle(
        code="cv_nombre_pages",
        categorie=Categorie.PIECES,
        libelle=f"CV de {maximum} pages maximum",
        resultat=resultat,
        consequence=reglement.consequence("cv_nombre_pages"),
        message=message,
        preuves=(Preuve(source="document", page=faits.premiere_page(TypePiece.CV)),),
    )


def _controle_signature(faits: FaitsPieces, reglement: Reglement) -> Controle:
    signee = faits.attestation_signee
    if signee is None:
        resultat = Resultat.INDETERMINE
        message = "Signature de l'attestation non détectée avec certitude : à vérifier."
    elif signee:
        resultat, message = Resultat.CONFORME, "Attestation de non-cumul signée."
    else:
        resultat, message = Resultat.NON_CONFORME, "L'attestation de non-cumul n'est pas signée."
    return Controle(
        code="attestation_signature",
        categorie=Categorie.PIECES,
        libelle="Attestation de non-cumul signée",
        resultat=resultat,
        consequence=reglement.consequence("attestation_signature"),
        message=message,
        preuves=(
            Preuve(
                source="document",
                page=faits.premiere_page(TypePiece.ATTESTATION_NON_CUMUL),
                extrait=faits.attestation_extrait,
            ),
        ),
    )


# --------------------------------------------------------------------------- statut


def calculer_statut(controles: Iterable[Controle]) -> Verdict:
    """Statut de recevabilité : NON_RECEVABLE > A_COMPLETER > RECEVABLE.

    Seuls les contrôles NON_CONFORMES dont la conséquence n'est pas un simple
    avertissement influent sur le statut.
    """
    effets = {c.effet for c in controles}
    if Consequence.NON_RECEVABLE in effets:
        return Verdict.NON_RECEVABLE
    if Consequence.A_COMPLETER in effets:
        return Verdict.A_COMPLETER
    return Verdict.RECEVABLE
