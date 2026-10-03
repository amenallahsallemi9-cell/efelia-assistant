"""Gestion d'erreurs homogène : toute erreur renvoie `{"erreur": {code, message, details}}`."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

MESSAGES_HTTP = {
    400: "Requête invalide.",
    404: "Ressource introuvable.",
    405: "Méthode non autorisée.",
    413: "Fichier trop volumineux.",
    415: "Type de fichier non pris en charge.",
    422: "Données invalides.",
    500: "Erreur interne du serveur.",
}


class ErreurApi(Exception):
    """Erreur métier exposée au client avec un code stable et un message en français."""

    def __init__(
        self, statut_http: int, code: str, message: str, details: Any | None = None
    ) -> None:
        super().__init__(message)
        self.statut_http = statut_http
        self.code = code
        self.message = message
        self.details = details


def _reponse(statut: int, code: str, message: str, details: Any | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=statut,
        content={"erreur": {"code": code, "message": message, "details": details}},
    )


def installer_gestionnaires(app: FastAPI) -> None:
    """Enregistre les gestionnaires d'exceptions sur l'application."""

    @app.exception_handler(ErreurApi)
    async def _erreur_api(_: Request, exc: ErreurApi) -> JSONResponse:
        return _reponse(exc.statut_http, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"champ": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()
        ]
        return _reponse(422, "VALIDATION", MESSAGES_HTTP[422], details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = MESSAGES_HTTP.get(exc.status_code, str(exc.detail))
        return _reponse(exc.status_code, f"HTTP_{exc.status_code}", message)

    @app.exception_handler(Exception)
    async def _inattendue(_: Request, exc: Exception) -> JSONResponse:
        logger.error("Erreur inattendue", exc_info=exc)
        return _reponse(500, "ERREUR_INTERNE", MESSAGES_HTTP[500])
