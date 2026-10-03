"""Lance le worker RQ qui exécute le pipeline des dossiers."""

from redis import Redis
from rq import Queue, Worker

from app.core.config import get_parametres
from app.core.logs import configurer_logs

NOM_FILE = "dossiers"


def main() -> None:
    """Démarre un worker sur la file `dossiers`."""
    parametres = get_parametres()
    configurer_logs(parametres.log_level)
    connexion = Redis.from_url(parametres.redis_url)
    Worker([Queue(NOM_FILE, connection=connexion)], connection=connexion).work(with_scheduler=True)


if __name__ == "__main__":
    main()
