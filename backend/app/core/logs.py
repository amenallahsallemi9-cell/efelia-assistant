"""Journalisation JSON.

Règle RGPD : on ne journalise **jamais** le texte des documents ni les données extraites,
seulement des identifiants, des statuts et des durées. Seuls les champs listés dans
`CHAMPS_AUTORISES` passés via `extra=` sont recopiés dans la sortie.
"""

import json
import logging
import sys
from datetime import UTC, datetime

CHAMPS_AUTORISES = frozenset(
    {"dossier_id", "etape", "statut", "duree_ms", "outil", "tour", "methode", "code", "chemin"}
)


#: Loggers tiers ramenés au niveau WARNING.
LOGGERS_TUS = ("httpx", "httpcore", "uvicorn.access")


class FormateurJson(logging.Formatter):
    """Formate chaque enregistrement en une ligne JSON, en ne gardant que les champs autorisés."""

    def format(self, record: logging.LogRecord) -> str:
        """Sérialise l'enregistrement de log."""
        donnees: dict[str, object] = {
            "horodatage": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "niveau": record.levelname,
            "module": record.name,
            "message": record.getMessage(),
        }
        for champ in CHAMPS_AUTORISES:
            if hasattr(record, champ):
                donnees[champ] = getattr(record, champ)
        if record.exc_info and record.exc_info[0] is not None:
            # Type d'exception uniquement : le message pourrait contenir du texte de document.
            donnees["exception"] = record.exc_info[0].__name__
        return json.dumps(donnees, ensure_ascii=False, default=str)


def configurer_logs(niveau: str = "INFO") -> None:
    """Installe le formateur JSON sur le logger racine."""
    gestionnaire = logging.StreamHandler(sys.stdout)
    gestionnaire.setFormatter(FormateurJson())
    racine = logging.getLogger()
    racine.handlers = [gestionnaire]
    racine.setLevel(niveau.upper())
    # Les clients HTTP (dont le SDK Cohere) journalisent les URL complètes : on les tait,
    # par précaution, pour qu'aucune donnée ne puisse fuiter par une chaîne de requête.
    for bavard in LOGGERS_TUS:
        logging.getLogger(bavard).setLevel(logging.WARNING)
