"""Routes des dossiers : dépôt, consultation, aperçus, instruction, suivi, effacement."""

import json
import uuid
from collections import Counter
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any, Literal

import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.dependances import Planificateur, get_planificateur, limiter_depots
from app.api.erreurs import ErreurApi
from app.api.schemas import (
    DecisionSortie,
    DossierDetail,
    DossierResume,
    FicheSortie,
    ListeDossiers,
    PageSortie,
    PieceSortie,
    ReponseDepot,
    ReponseInstruction,
    Statistiques,
    TraceSortie,
)
from app.core.config import Parametres, get_parametres
from app.core.reglement import get_reglement
from app.db.modeles import Decision, Dossier, TraceAgent
from app.db.session import get_session
from app.domain.modeles import StatutPipeline, Verdict
from app.domain.noms import nom_fichier_attendu
from app.domain.regles import Reglement
from app.schemas import FicheDeclaree
from app.services.apercu import rendre_apercu
from app.services.depot import ErreurDepot, creer_dossier
from app.services.effacement import effacer_dossier
from app.workers.pipeline import canal_evenements

routeur = APIRouter(prefix="/dossiers", tags=["dossiers"])

SessionDep = Annotated[Session, Depends(get_session)]
ParametresDep = Annotated[Parametres, Depends(get_parametres)]
ReglementDep = Annotated[Reglement, Depends(get_reglement)]
PlanificateurDep = Annotated[Planificateur, Depends(get_planificateur)]

STATUTS_TERMINAUX = {StatutPipeline.INSTRUIT, StatutPipeline.ERREUR}
ETAPES_AFFICHEES = ["RECU", "EXTRAIT", "CLASSE", "LU", "INDEXE", "INSTRUIT"]
DUREE_MAX_FLUX_S = 15 * 60
INTERVALLE_PING_S = 15


def _dossier(session: Session, dossier_id: uuid.UUID) -> Dossier:
    dossier = session.get(Dossier, dossier_id)
    if dossier is None:
        raise ErreurApi(404, "DOSSIER_INTROUVABLE", "Ce dossier n'existe pas ou a été supprimé.")
    return dossier


def _attendu(dossier: Dossier, reglement: Reglement) -> str:
    return nom_fichier_attendu(reglement.prefixe_nom_fichier, dossier.nom, dossier.prenom)


# --------------------------------------------------------------------------- dépôt


@routeur.post(
    "",
    response_model=ReponseDepot,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Déposer un dossier (PDF + fiche)",
    dependencies=[Depends(limiter_depots)],
)
async def deposer(
    session: SessionDep,
    parametres: ParametresDep,
    reglement: ReglementDep,
    planificateur: PlanificateurDep,
    fichier: Annotated[UploadFile, File(description="Dossier complet, PDF unique (20 Mo max).")],
    fiche: Annotated[str, Form(description="Fiche déclarative au format JSON.")],
    consentement: Annotated[
        bool, Form(description="Consentement au traitement des données (obligatoire).")
    ] = False,
) -> ReponseDepot:
    """Valide le fichier et la fiche, enregistre le dossier et lance le traitement."""
    if not consentement:
        raise ErreurApi(
            422,
            "CONSENTEMENT_REQUIS",
            "Le consentement au traitement des données est nécessaire pour déposer un dossier.",
        )
    try:
        fiche_validee = FicheDeclaree.model_validate_json(fiche)
    except ValidationError as exc:
        details = [
            {"champ": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()
        ]
        raise ErreurApi(
            422, "FICHE_INVALIDE", "La fiche déclarative est invalide.", details
        ) from exc

    limite = parametres.max_taille_mo * 1024 * 1024
    contenu = await fichier.read(limite + 1)
    try:
        dossier = creer_dossier(
            session,
            fiche_validee,
            fichier.filename or "sans_nom.pdf",
            contenu,
            parametres,
            reglement,
        )
    except ErreurDepot as exc:
        raise ErreurApi(exc.statut_http, exc.code, exc.message) from exc

    reponse = ReponseDepot(
        id=dossier.id,
        statut_pipeline=dossier.statut_pipeline,
        nom_fichier_attendu=_attendu(dossier, reglement),
        message="Dossier reçu : l'analyse est en cours.",
    )
    planificateur.planifier_traitement(dossier.id)
    return reponse


# --------------------------------------------------------------------------- consultation


def _dernieres_decisions() -> Any:
    rang = (
        func.row_number()
        .over(
            partition_by=Decision.dossier_id,
            order_by=(Decision.created_at.desc(), Decision.id.desc()),
        )
        .label("rang")
    )
    return select(
        Decision.dossier_id,
        Decision.statut_regles,
        Decision.garde_fou_declenche,
        Decision.controles,
        rang,
    ).subquery()


TRIS = {
    "recent": (Dossier.created_at.desc(),),
    "ancien": (Dossier.created_at.asc(),),
    "nom": (Dossier.nom.asc(), Dossier.prenom.asc()),
    "reception": (Dossier.date_reception.asc(),),
}


@routeur.get("", response_model=ListeDossiers, summary="Lister les dossiers")
def lister(
    session: SessionDep,
    statut_pipeline: StatutPipeline | None = None,
    verdict: Verdict | None = None,
    recherche: Annotated[str | None, Query(max_length=100)] = None,
    tri: Literal["recent", "ancien", "nom", "reception", "verdict"] = "recent",
    page: Annotated[int, Query(ge=1)] = 1,
    taille: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ListeDossiers:
    """Liste paginée, filtrable par statut du pipeline, verdict et nom."""
    derniere = _dernieres_decisions()
    requete: Select[Any] = select(
        Dossier, derniere.c.statut_regles, derniere.c.garde_fou_declenche
    ).outerjoin(derniere, and_(derniere.c.dossier_id == Dossier.id, derniere.c.rang == 1))
    if statut_pipeline is not None:
        requete = requete.where(Dossier.statut_pipeline == statut_pipeline)
    if verdict is not None:
        requete = requete.where(derniere.c.statut_regles == verdict)
    if recherche:
        motif = "%" + recherche.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        requete = requete.where(
            or_(
                Dossier.nom.ilike(motif, escape="\\"),
                Dossier.prenom.ilike(motif, escape="\\"),
                Dossier.formation.ilike(motif, escape="\\"),
            )
        )
    total = session.scalar(select(func.count()).select_from(requete.subquery())) or 0
    ordre = (
        (derniere.c.statut_regles.asc().nulls_last(), Dossier.created_at.desc())
        if tri == "verdict"
        else TRIS[tri]
    )
    lignes = session.execute(requete.order_by(*ordre).offset((page - 1) * taille).limit(taille))
    elements = [
        DossierResume.model_validate(dossier).model_copy(
            update={"verdict": statut, "garde_fou_declenche": bool(garde_fou)}
        )
        for dossier, statut, garde_fou in lignes
    ]
    return ListeDossiers(elements=elements, total=total, page=page, taille=taille)


@routeur.get("/statistiques", response_model=Statistiques, summary="Compteurs du tableau de bord")
def statistiques(session: SessionDep, reglement: ReglementDep) -> Statistiques:
    """Répartition par verdict et par étape, pièces obligatoires le plus souvent manquantes."""
    derniere = _dernieres_decisions()
    decisions = session.execute(
        select(
            derniere.c.statut_regles, derniere.c.garde_fou_declenche, derniere.c.controles
        ).where(derniere.c.rang == 1)
    ).all()
    par_statut = dict(
        session.execute(
            select(Dossier.statut_pipeline, func.count()).group_by(Dossier.statut_pipeline)
        ).all()
    )
    manquantes: Counter[str] = Counter()
    for _, _, controles in decisions:
        for controle in controles or []:
            if controle["code"].startswith("piece_") and controle["resultat"] == "NON_CONFORME":
                manquantes[controle["code"].removeprefix("piece_")] += 1
    libelles = {p.type.value: p.libelle for p in reglement.pieces_obligatoires}
    return Statistiques(
        total=sum(par_statut.values()),
        par_verdict={v.value: sum(1 for d in decisions if d[0] is v) for v in Verdict},
        par_statut_pipeline={s.value: par_statut.get(s, 0) for s in StatutPipeline},
        pieces_manquantes=[
            {"type": t, "libelle": libelles.get(t, t), "nombre": n}
            for t, n in manquantes.most_common()
        ],
        garde_fous_declenches=sum(1 for d in decisions if d[1]),
    )


@routeur.get("/{dossier_id}", response_model=DossierDetail, summary="Détail d'un dossier")
def detail(dossier_id: uuid.UUID, session: SessionDep, reglement: ReglementDep) -> DossierDetail:
    """Fiche, pages, pièces et données extraites, dernière décision."""
    dossier = _dossier(session, dossier_id)
    derniere = max(dossier.decisions, key=lambda d: (d.created_at, d.id), default=None)
    return DossierDetail(
        id=dossier.id,
        statut_pipeline=dossier.statut_pipeline,
        message_erreur=dossier.message_erreur,
        nb_pages=dossier.nb_pages,
        created_at=dossier.created_at,
        nom_fichier_attendu=_attendu(dossier, reglement),
        fiche=FicheSortie.model_validate(dossier),
        pages=[PageSortie.model_validate(p) for p in dossier.pages],
        pieces=[
            PieceSortie.model_validate(p)
            for p in sorted(dossier.pieces, key=lambda p: min(p.pages))
        ],
        decision=DecisionSortie.model_validate(derniere) if derniere else None,
        nb_decisions=len(dossier.decisions),
    )


@routeur.get(
    "/{dossier_id}/pages/{numero}/image",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
    summary="Aperçu PNG d'une page",
)
def image_page(
    dossier_id: uuid.UUID,
    numero: int,
    session: SessionDep,
    surligner: Annotated[
        str | None, Query(max_length=300, description="Extrait à surligner (preuve).")
    ] = None,
) -> Response:
    """Aperçu de la page ; l'extrait demandé est surligné ; une page sensible est masquée."""
    dossier = _dossier(session, dossier_id)
    page = next((p for p in dossier.pages if p.numero == numero), None)
    try:
        apercu = rendre_apercu(
            Path(dossier.chemin_fichier),
            numero,
            surligner=surligner,
            masquer=bool(page and page.sensible),
        )
    except (IndexError, FileNotFoundError) as exc:
        raise ErreurApi(404, "PAGE_INTROUVABLE", f"La page {numero} n'existe pas.") from exc
    return Response(
        apercu.png,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=300", "X-Zones-Surlignees": str(apercu.zones)},
    )


# --------------------------------------------------------------------------- instruction


@routeur.post(
    "/{dossier_id}/instruire",
    response_model=ReponseInstruction,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Relancer l'agent",
)
def instruire(
    dossier_id: uuid.UUID, session: SessionDep, planificateur: PlanificateurDep
) -> ReponseInstruction:
    """Nouvelle instruction (l'historique des décisions est conservé)."""
    dossier = _dossier(session, dossier_id)
    if dossier.statut_pipeline not in STATUTS_TERMINAUX:
        raise ErreurApi(
            409, "TRAITEMENT_EN_COURS", "Le dossier est en cours de traitement : réessayez ensuite."
        )
    planificateur.planifier_instruction(dossier.id)
    return ReponseInstruction(id=dossier.id, message="Nouvelle instruction planifiée.")


@routeur.get("/{dossier_id}/trace", response_model=list[TraceSortie], summary="Trace de l'agent")
def trace(dossier_id: uuid.UUID, session: SessionDep) -> list[TraceSortie]:
    """Chronologie des appels d'outils de la dernière instruction."""
    _dossier(session, dossier_id)
    traces = session.scalars(
        select(TraceAgent).where(TraceAgent.dossier_id == dossier_id).order_by(TraceAgent.ordre)
    )
    return [TraceSortie.model_validate(t) for t in traces]


async def _fermer(abonnement: Any, client: redis_async.Redis) -> None:
    await abonnement.aclose()
    await client.aclose()


def _sse(donnees: dict[str, Any], evenement: str = "progression") -> str:
    return f"event: {evenement}\ndata: {json.dumps(donnees, ensure_ascii=False, default=str)}\n\n"


@routeur.get(
    "/{dossier_id}/evenements",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
    summary="Progression en temps réel (Server-Sent Events)",
)
async def evenements(
    dossier_id: uuid.UUID, session: SessionDep, parametres: ParametresDep
) -> StreamingResponse:
    """Émet l'état courant puis chaque étape franchie, jusqu'à INSTRUIT ou ERREUR."""
    # Abonnement AVANT la lecture de l'état : aucun événement ne peut être manqué.
    client = redis_async.from_url(parametres.redis_url)
    abonnement = client.pubsub()
    await abonnement.subscribe(canal_evenements(dossier_id))
    try:
        dossier = _dossier(session, dossier_id)
    except ErreurApi:
        await _fermer(abonnement, client)
        raise
    initial = {
        "dossier_id": str(dossier.id),
        "statut": dossier.statut_pipeline.value,
        "message": dossier.message_erreur,
        "etapes": ETAPES_AFFICHEES,
    }
    terminal = dossier.statut_pipeline in STATUTS_TERMINAUX

    async def flux() -> AsyncIterator[str]:
        try:
            yield _sse(initial)
            if terminal:
                return
            attente = 0.0
            while attente < DUREE_MAX_FLUX_S:
                message = await abonnement.get_message(
                    ignore_subscribe_messages=True, timeout=INTERVALLE_PING_S
                )
                if message is None:
                    attente += INTERVALLE_PING_S
                    yield ": ping\n\n"
                    continue
                donnees = json.loads(message["data"])
                yield _sse(donnees)
                if donnees.get("statut") in {s.value for s in STATUTS_TERMINAUX}:
                    return
        finally:
            await _fermer(abonnement, client)

    return StreamingResponse(
        flux(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------------- effacement


@routeur.delete(
    "/{dossier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Supprimer un dossier (droit à l'effacement)",
)
def supprimer(dossier_id: uuid.UUID, session: SessionDep, parametres: ParametresDep) -> Response:
    """Efface le fichier, le texte, les données extraites, les embeddings et les traces."""
    effacer_dossier(session, _dossier(session, dossier_id), parametres.stockage_dir)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
