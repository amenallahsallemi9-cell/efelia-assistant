"""Point d'entrée de l'API FastAPI."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.erreurs import installer_gestionnaires
from app.api.routes import sante
from app.core.config import get_parametres
from app.core.logs import configurer_logs

DESCRIPTION = """
Instruction automatique de la **recevabilité** des dossiers de la Bourse Excellence
EFELIA Côte d'Azur 2026.

« RECEVABLE » signifie que le dossier est complet et conforme. L'application ne prédit
**jamais** la décision du jury.

*Projet étudiant indépendant, non affilié à EFELIA. Le règlement officiel fait foi.*
"""


def creer_app() -> FastAPI:
    """Construit l'application (utilisé aussi par les tests)."""
    parametres = get_parametres()
    configurer_logs(parametres.log_level)

    app = FastAPI(
        title="EFELIA — Agent d'instruction",
        version=__version__,
        description=DESCRIPTION,
        docs_url="/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=parametres.liste_cors,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    installer_gestionnaires(app)
    app.include_router(sante.routeur, prefix="/api")
    return app


app = creer_app()
