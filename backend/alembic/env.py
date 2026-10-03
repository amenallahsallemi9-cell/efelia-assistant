"""Environnement Alembic : l'URL vient des paramètres, sauf si `sqlalchemy.url` est imposée."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_parametres
from app.db.modeles import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configurer_logs", True):
    fileConfig(config.config_file_name)

if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_parametres().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Génère le SQL sans connexion."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Applique les migrations sur la base."""
    moteur = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with moteur.connect() as connexion:
        context.configure(connection=connexion, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
