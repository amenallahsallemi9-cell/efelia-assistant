"""Les logs ne doivent contenir que des identifiants et des statuts (RGPD)."""

import json
import logging

from app.core.logs import FormateurJson


def _enregistrement(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "Étape terminée", None, None)
    for cle, valeur in extra.items():
        setattr(record, cle, valeur)
    return record


def test_seuls_les_champs_autorises_sont_journalises() -> None:
    record = _enregistrement(
        dossier_id="abc", etape="EXTRAIT", texte="Relevé bancaire IBAN FR76…", nom="Dupont"
    )
    sortie = json.loads(FormateurJson().format(record))
    assert sortie["dossier_id"] == "abc"
    assert sortie["etape"] == "EXTRAIT"
    assert "texte" not in sortie
    assert "nom" not in sortie
    assert "IBAN" not in json.dumps(sortie)


def test_exception_reduite_a_son_type() -> None:
    try:
        raise ValueError("contenu sensible du document")
    except ValueError:
        import sys

        record = _enregistrement()
        record.exc_info = sys.exc_info()
    sortie = FormateurJson().format(record)
    assert json.loads(sortie)["exception"] == "ValueError"
    assert "contenu sensible" not in sortie


def test_clients_http_tus() -> None:
    from app.core.logs import configurer_logs

    configurer_logs("DEBUG")
    for nom in ("httpx", "httpcore", "uvicorn.access"):
        assert not logging.getLogger(nom).isEnabledFor(logging.INFO)
