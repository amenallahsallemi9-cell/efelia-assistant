"""Route de santé : état de l'API, de la base, de Redis et du fournisseur LLM."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependances import ClientRedis, get_redis
from app.core.config import Parametres, get_parametres
from app.db.session import get_session

logger = logging.getLogger(__name__)
routeur = APIRouter(tags=["santé"])

Etat = Literal["ok", "erreur"]


class EtatComposant(BaseModel):
    """État d'un composant."""

    etat: Etat
    detail: str | None = None


class ReponseSante(BaseModel):
    """Réponse de `GET /api/sante`."""

    statut: Literal["ok", "degrade"]
    version: str
    mode_demo: bool
    base: EtatComposant
    redis: EtatComposant
    fournisseur_llm: EtatComposant


def _verifier_base(session: Session) -> EtatComposant:
    try:
        session.execute(text("SELECT 1"))
        extension = session.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
    except Exception:
        logger.warning("Base de données injoignable")
        return EtatComposant(etat="erreur", detail="Base de données injoignable.")
    if not extension:
        return EtatComposant(etat="erreur", detail="Extension pgvector absente.")
    return EtatComposant(etat="ok")


def _verifier_redis(client: ClientRedis) -> EtatComposant:
    try:
        client.ping()
    except Exception:
        logger.warning("Redis injoignable")
        return EtatComposant(etat="erreur", detail="Redis injoignable.")
    return EtatComposant(etat="ok")


def _verifier_fournisseur(parametres: Parametres) -> EtatComposant:
    fournisseur = parametres.fournisseur_effectif
    if fournisseur == "fake":
        return EtatComposant(etat="ok", detail="Mode démo (FakeProvider, sans appel réseau).")
    if not parametres.cohere_api_key:
        return EtatComposant(
            etat="erreur", detail="LLM_PROVIDER=cohere mais COHERE_API_KEY absente."
        )
    return EtatComposant(etat="ok", detail="Cohere configuré.")


@routeur.get("/sante", response_model=ReponseSante, summary="État des services")
def sante(
    session: Annotated[Session, Depends(get_session)],
    client_redis: Annotated[ClientRedis, Depends(get_redis)],
    parametres: Annotated[Parametres, Depends(get_parametres)],
) -> ReponseSante:
    """Vérifie la base (et pgvector), Redis et la configuration du fournisseur LLM."""
    from app import __version__

    base = _verifier_base(session)
    redis_etat = _verifier_redis(client_redis)
    fournisseur = _verifier_fournisseur(parametres)
    tout_ok = all(c.etat == "ok" for c in (base, redis_etat, fournisseur))
    return ReponseSante(
        statut="ok" if tout_ok else "degrade",
        version=__version__,
        mode_demo=parametres.mode_demo,
        base=base,
        redis=redis_etat,
        fournisseur_llm=fournisseur,
    )
