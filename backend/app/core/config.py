"""Configuration de l'application, lue depuis les variables d'environnement (.env)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Parametres(BaseSettings):
    """Paramètres d'exécution. Aucun secret n'est codé en dur : tout vient de l'environnement."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://efelia:efelia@localhost:5432/efelia"
    test_database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: Literal["auto", "cohere", "fake"] = "auto"
    cohere_api_key: SecretStr | None = None

    stockage_dir: Path = Path("/data/dossiers")
    max_taille_mo: int = Field(default=20, gt=0)
    max_pages: int = Field(default=60, gt=0)
    retention_jours: int = Field(default=180, gt=0)

    log_level: str = "INFO"
    cors_origines: str = "http://localhost:3000,http://localhost:5173"
    regles_fichier: Path = Path("/config/regles_2026.yaml")
    reglement_texte: Path = Path("/config/reglement_2026.md")

    @field_validator("cohere_api_key", mode="before")
    @classmethod
    def _cle_vide_absente(cls, valeur: object) -> object:
        """Une clé vide dans le .env équivaut à une clé absente."""
        if isinstance(valeur, str) and not valeur.strip():
            return None
        return valeur

    @property
    def fournisseur_effectif(self) -> Literal["cohere", "fake"]:
        """Fournisseur réellement utilisé : en mode `auto`, Cohere seulement si une clé existe."""
        if self.llm_provider == "auto":
            return "cohere" if self.cohere_api_key else "fake"
        return self.llm_provider

    @property
    def mode_demo(self) -> bool:
        """Vrai quand l'application tourne sans LLM réel (FakeProvider)."""
        return self.fournisseur_effectif == "fake"

    @property
    def liste_cors(self) -> list[str]:
        """Origines autorisées pour le CORS."""
        return [o.strip() for o in self.cors_origines.split(",") if o.strip()]


@lru_cache
def get_parametres() -> Parametres:
    """Retourne les paramètres (mis en cache pour toute la durée du processus)."""
    return Parametres()
