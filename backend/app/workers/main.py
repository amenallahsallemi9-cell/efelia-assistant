"""Lance le worker RQ qui exécute le pipeline des dossiers et la purge quotidienne."""

from redis import Redis
from rq import Queue, Worker

from app.core.config import get_parametres
from app.core.logs import configurer_logs
from app.workers.file import NOM_FILE
from app.workers.purge import planifier_purge


def main() -> None:
    """Démarre un worker sur la file `dossiers` (avec planificateur pour la purge)."""
    parametres = get_parametres()
    configurer_logs(parametres.log_level)
    connexion = Redis.from_url(parametres.redis_url)
    file = Queue(NOM_FILE, connection=connexion)
    planifier_purge(file)
    Worker([file], connection=connexion).work(with_scheduler=True)


if __name__ == "__main__":
    main()
