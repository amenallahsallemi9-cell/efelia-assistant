"""Dépendances FastAPI partagées."""

from functools import lru_cache
from typing import TYPE_CHECKING

from redis import Redis

from app.core.config import get_parametres

# `Redis` n'est générique que pour le typage statique (stubs) : alias compatible à l'exécution.
if TYPE_CHECKING:
    ClientRedis = Redis[bytes]
else:
    ClientRedis = Redis


@lru_cache
def get_redis() -> ClientRedis:
    """Client Redis partagé (connexion paresseuse)."""
    return Redis.from_url(get_parametres().redis_url, socket_connect_timeout=2)
