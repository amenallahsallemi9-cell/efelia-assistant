"""Sécurité HTTP : limitation de débit, en-têtes de sécurité, journal d'accès sans données.

Le journal d'accès n'enregistre JAMAIS la chaîne de requête : `?surligner=` contient
un extrait de document. Le journal d'accès d'uvicorn est donc désactivé au profit
de celui-ci.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response

logger = logging.getLogger("app.acces")

EN_TETES_SECURITE = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
CSP_API = "default-src 'none'; frame-ancestors 'none'"
CHEMINS_DOCUMENTATION = ("/docs", "/redoc")


def autoriser(client: Any, cle: str, limite: int, fenetre_s: int) -> tuple[bool, int]:
    """Fenêtre fixe dans Redis : (autorisé ?, secondes avant la prochaine fenêtre).

    Si Redis est indisponible, la requête est autorisée (disponibilité d'abord) et
    l'incident est journalisé.
    """
    compteur = f"limite:{cle}:{int(time.time()) // fenetre_s}"
    try:
        pipeline = client.pipeline()
        pipeline.incr(compteur)
        pipeline.expire(compteur, fenetre_s)
        nombre, _ = pipeline.execute()
    except Exception:
        logger.warning("Limitation de débit indisponible (Redis)")
        return True, 0
    if int(nombre) > limite:
        return False, fenetre_s - int(time.time()) % fenetre_s
    return True, 0


def adresse_client(requete: Request) -> str:
    """Adresse du client (uvicorn applique X-Forwarded-For du proxy nginx)."""
    return requete.client.host if requete.client else "inconnue"


async def intergiciel_securite(
    requete: Request, suivant: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Ajoute les en-têtes de sécurité et écrit le journal d'accès (sans chaîne de requête)."""
    debut = time.perf_counter()
    reponse = await suivant(requete)
    for nom, valeur in EN_TETES_SECURITE.items():
        reponse.headers.setdefault(nom, valeur)
    if not requete.url.path.startswith(CHEMINS_DOCUMENTATION):
        reponse.headers.setdefault("Content-Security-Policy", CSP_API)
    if requete.url.path != "/api/sante":
        logger.info(
            "Requête",
            extra={
                "methode": requete.method,
                "chemin": requete.url.path,
                "code": reponse.status_code,
                "duree_ms": round((time.perf_counter() - debut) * 1000),
            },
        )
    return reponse
