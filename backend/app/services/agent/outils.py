"""Les 9 outils de l'agent : schéma JSON (via Pydantic), fonction Python, exécution sûre.

Toute erreur (outil inconnu, JSON invalide, argument manquant, mauvais dossier, panne)
est renvoyée au LLM sous la forme `{"erreur": "..."}` : la boucle continue et l'agent
peut se corriger. Un outil ne peut agir que sur le dossier en cours d'instruction.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.domain.coherence import verifier_coherence
from app.domain.modeles import PIECES_SENSIBLES, SourceMorceau, TypePiece, Verdict
from app.domain.regles import verifier_eligibilite, verifier_format, verifier_pieces
from app.providers.base import AppelOutil, Outil, schema_compatible
from app.services.agent.contexte import ContexteAgent, PropositionDecision, controle_vers_dict
from app.services.recherche import Resultat, nettoyer_question, rechercher

logger = logging.getLogger(__name__)
PARIS = ZoneInfo("Europe/Paris")

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArgsDossier(_Args):
    """Identifiant du dossier en cours d'instruction."""

    dossier_id: str = Field(description="Identifiant (UUID) du dossier en cours d'instruction.")


class ArgsLirePiece(ArgsDossier):
    """Pièce à lire."""

    type_piece: TypePiece = Field(description="Type de la pièce à lire.")


class ArgsRechercheReglement(_Args):
    """Question sur le règlement."""

    question: Question = Field(description="Question en français sur le règlement.")


class ArgsRechercheDossier(ArgsDossier):
    """Question sur le contenu du dossier."""

    question: Question = Field(description="Ce que l'on cherche dans le dossier.")


class MotifPropose(_Args):
    """Motif rédigé par l'agent, avec sa preuve."""

    message: Annotated[str, StringConstraints(min_length=1, max_length=600)]
    page: int | None = Field(default=None, description="Page du dossier qui le prouve.")
    extrait: Annotated[str, StringConstraints(max_length=300)] | None = None


class ConseilPropose(_Args):
    """Conseil concret, fondé sur le règlement et le dossier."""

    categorie: Literal["lettre", "cv", "pieces", "general"]
    texte: Annotated[str, StringConstraints(min_length=1, max_length=600)]
    page: int | None = Field(default=None, description="Page du dossier concernée.")


class ArgsDecision(ArgsDossier):
    """Décision proposée (le statut final est recalculé par les règles)."""

    statut: Verdict
    motifs: list[MotifPropose] = Field(max_length=20)
    conseils: list[ConseilPropose] = Field(max_length=20)


class ErreurOutil(Exception):
    """Erreur renvoyée au LLM."""


# --------------------------------------------------------------------------- fonctions


def _resultat_recherche(resultats: list[Resultat]) -> dict[str, Any]:
    return {
        "resultats": [
            {
                "texte": r.texte,
                "page": r.page,
                "piece": r.type_piece.value if r.type_piece else None,
                "section": r.section,
                "score": r.score,
            }
            for r in resultats
        ]
    }


def lire_fiche(contexte: ContexteAgent, _: ArgsDossier) -> dict[str, Any]:
    """Informations déclarées, pages et pièces détectées, alertes d'injection."""
    d = contexte.dossier
    return {
        "dossier_id": str(d.id),
        "nom": d.nom,
        "prenom": d.prenom,
        "formation": d.formation,
        "inscrit_uca": d.inscrit_uca,
        "heures_ia": d.heures_ia,
        "alternance": d.alternance,
        "autre_bourse": d.autre_bourse,
        "autre_bourse_libelle": d.autre_bourse_libelle,
        "nom_fichier": d.nom_fichier,
        "date_reception": d.date_reception.astimezone(PARIS).isoformat(),
        "nb_pages": d.nb_pages,
        "pages": [
            {
                "numero": p.numero,
                "type_piece": p.type_piece.value if p.type_piece else None,
                "methode": p.methode.value,
                "sensible": p.sensible,
            }
            for p in d.pages
        ],
        "pieces": [
            {"type": p.type.value, "pages": p.pages, "confiance": p.confiance.value}
            for p in d.pieces
        ],
        "alertes_injection": alertes_injection(contexte),
    }


def alertes_injection(contexte: ContexteAgent) -> list[dict[str, Any]]:
    """Passages des documents qui ressemblent à des consignes adressées à une IA."""
    return [
        alerte
        for piece in contexte.dossier.pieces
        for alerte in (piece.donnees_extraites or {}).get("alertes_injection", [])
    ]


def _controles(controles: list[Any]) -> dict[str, Any]:
    return {"controles": [controle_vers_dict(c) for c in controles]}


def outil_verifier_eligibilite(contexte: ContexteAgent, _: ArgsDossier) -> dict[str, Any]:
    """Les 4 conditions d'éligibilité."""
    return _controles(verifier_eligibilite(contexte.fiche(), contexte.reglement))


def outil_verifier_format(contexte: ContexteAgent, _: ArgsDossier) -> dict[str, Any]:
    """Nom du fichier et date de réception."""
    d = contexte.dossier
    return _controles(
        verifier_format(d.nom_fichier, d.date_reception, contexte.fiche(), contexte.reglement)
    )


def outil_verifier_pieces(contexte: ContexteAgent, args: ArgsDossier) -> dict[str, Any]:
    """Pièces obligatoires et facultatives, longueur du CV, signature."""
    faits_pieces, _ = contexte.faits()
    return _controles(verifier_pieces(faits_pieces, contexte.reglement))


def outil_lire_piece(contexte: ContexteAgent, args: ArgsLirePiece) -> dict[str, Any]:
    """Données structurées extraites d'une pièce."""
    piece = next((p for p in contexte.dossier.pieces if p.type is args.type_piece), None)
    if piece is None:
        return {"present": False, "type_piece": args.type_piece.value}
    if piece.type in PIECES_SENSIBLES:
        return {
            "present": True,
            "type_piece": piece.type.value,
            "pages": piece.pages,
            "note": "Justificatif sensible : seul son type est connu, "
            "son contenu n'est pas lu (RGPD).",
        }
    return {
        "present": True,
        "type_piece": piece.type.value,
        "pages": piece.pages,
        "confiance": piece.confiance.value,
        "donnees": piece.donnees_extraites,
    }


def outil_verifier_coherence(contexte: ContexteAgent, args: ArgsDossier) -> dict[str, Any]:
    """Contrôles croisés fiche ↔ documents."""
    _, faits_coherence = contexte.faits()
    return _controles(verifier_coherence(contexte.fiche(), faits_coherence, contexte.reglement))


def outil_rechercher_reglement(
    contexte: ContexteAgent, args: ArgsRechercheReglement
) -> dict[str, Any]:
    """Passages du règlement les plus pertinents (top 3 après reranking)."""
    resultats = rechercher(
        contexte.session,
        contexte.fournisseurs,
        nettoyer_question(args.question),
        SourceMorceau.REGLEMENT,
        k=3,
    )
    return _resultat_recherche(resultats)


def outil_rechercher_dans_dossier(
    contexte: ContexteAgent, args: ArgsRechercheDossier
) -> dict[str, Any]:
    """Passages du dossier, avec page et pièce."""
    resultats = rechercher(
        contexte.session,
        contexte.fournisseurs,
        nettoyer_question(args.question),
        SourceMorceau.DOSSIER,
        contexte.dossier.id,
        k=3,
    )
    return _resultat_recherche(resultats)


def outil_enregistrer_decision(contexte: ContexteAgent, args: ArgsDecision) -> dict[str, Any]:
    """Enregistre la proposition de l'agent (une seule fois) et renvoie le statut des règles."""
    if contexte.proposition is not None:
        raise ErreurOutil("La décision a déjà été enregistrée : un seul appel est autorisé.")
    nb_pages = contexte.dossier.nb_pages or 0

    def _page(page: int | None) -> int | None:
        return page if page is not None and 1 <= page <= nb_pages else None

    contexte.proposition = PropositionDecision(
        statut=args.statut,
        motifs=[{**m.model_dump(), "page": _page(m.page)} for m in args.motifs],
        conseils=[{**c.model_dump(), "page": _page(c.page)} for c in args.conseils],
    )
    statut_regles = contexte.instruction().statut
    ecart = statut_regles is not args.statut
    return {
        "enregistree": True,
        "statut_propose": args.statut.value,
        "statut_retenu": statut_regles.value,
        "ecart": ecart,
        "explication": (
            "Le statut est toujours calculé par les règles du règlement : il s'applique."
            + (" Ta proposition diffère : explique l'écart dans ton rapport." if ecart else "")
        ),
    }


# --------------------------------------------------------------------------- registre


@dataclass(frozen=True)
class DefinitionOutil:
    """Outil : description, modèle d'arguments et fonction."""

    nom: str
    description: str
    arguments: type[BaseModel]
    fonction: Callable[[ContexteAgent, Any], dict[str, Any]]

    def vers_outil(self) -> Outil:
        """Définition neutre, transmise au fournisseur."""
        return Outil(
            self.nom, self.description, schema_compatible(self.arguments.model_json_schema())
        )


DEFINITIONS: tuple[DefinitionOutil, ...] = (
    DefinitionOutil(
        "lire_fiche",
        "Informations déclarées par l'étudiant·e, liste des pages avec leur type, pièces "
        "détectées et alertes d'injection de prompt.",
        ArgsDossier,
        lire_fiche,
    ),
    DefinitionOutil(
        "verifier_eligibilite",
        "Vérifie les 4 conditions d'éligibilité (inscription UCA, 24 h d'IA, hors "
        "alternance, pas d'autre bourse hors CROUS sur critères sociaux).",
        ArgsDossier,
        outil_verifier_eligibilite,
    ),
    DefinitionOutil(
        "verifier_format",
        "Vérifie le nom du fichier et la date de réception (date limite).",
        ArgsDossier,
        outil_verifier_format,
    ),
    DefinitionOutil(
        "verifier_pieces",
        "Vérifie la présence des pièces obligatoires et facultatives, la longueur du CV "
        "et la signature de l'attestation.",
        ArgsDossier,
        outil_verifier_pieces,
    ),
    DefinitionOutil(
        "lire_piece",
        "Renvoie les données structurées extraites d'une pièce (avec pages et extraits).",
        ArgsLirePiece,
        outil_lire_piece,
    ),
    DefinitionOutil(
        "verifier_coherence",
        "Contrôles croisés entre la fiche et les documents (identité, année, "
        "établissement, thèmes de la lettre, relevés, attestation).",
        ArgsDossier,
        outil_verifier_coherence,
    ),
    DefinitionOutil(
        "rechercher_reglement",
        "Recherche dans le règlement officiel 2026 (3 passages les plus pertinents).",
        ArgsRechercheReglement,
        outil_rechercher_reglement,
    ),
    DefinitionOutil(
        "rechercher_dans_dossier",
        "Recherche dans le texte du dossier (3 passages, avec page et pièce).",
        ArgsRechercheDossier,
        outil_rechercher_dans_dossier,
    ),
    DefinitionOutil(
        "enregistrer_decision",
        "Enregistre ta proposition de statut, tes motifs (avec page et extrait) et tes "
        "conseils. Un seul appel, à la fin. Le statut final est recalculé par les règles.",
        ArgsDecision,
        outil_enregistrer_decision,
    ),
)
OUTILS: dict[str, DefinitionOutil] = {d.nom: d for d in DEFINITIONS}


def outils_pour_llm() -> list[Outil]:
    """Définitions transmises au LLM."""
    return [d.vers_outil() for d in DEFINITIONS]


def executer_outil(contexte: ContexteAgent, appel: AppelOutil) -> dict[str, Any]:
    """Exécute un appel d'outil ; toute erreur devient un résultat `{"erreur": ...}`."""
    definition = OUTILS.get(appel.nom)
    if definition is None:
        return {
            "erreur": f"Outil inconnu : « {appel.nom} ». Outils disponibles : " + ", ".join(OUTILS)
        }
    try:
        brut = json.loads(appel.arguments or "{}")
    except json.JSONDecodeError:
        return {"erreur": "Arguments invalides : JSON mal formé."}
    try:
        args = definition.arguments.model_validate(brut)
    except ValidationError as exc:
        details = "; ".join(
            f"{'.'.join(map(str, e['loc'])) or 'arguments'} : {e['msg']}" for e in exc.errors()
        )
        return {"erreur": f"Arguments invalides pour {appel.nom} — {details}"}
    if isinstance(args, ArgsDossier) and args.dossier_id != str(contexte.dossier.id):
        return {"erreur": "Accès refusé : seul le dossier en cours d'instruction est accessible."}
    try:
        return definition.fonction(contexte, args)
    except ErreurOutil as exc:
        return {"erreur": str(exc)}
    except Exception as exc:
        logger.error(
            "Échec d'un outil",
            exc_info=exc,
            extra={"dossier_id": str(contexte.dossier.id), "outil": appel.nom},
        )
        return {"erreur": f"Erreur interne de l'outil {appel.nom}."}
