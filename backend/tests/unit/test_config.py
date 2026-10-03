"""Tests des paramètres d'exécution."""

import pytest
from pydantic import SecretStr

from app.core.config import Parametres


@pytest.mark.parametrize(
    ("provider", "cle", "attendu"),
    [
        ("auto", None, "fake"),
        ("auto", "", "fake"),
        ("auto", "   ", "fake"),
        ("auto", "cle-secrete", "cohere"),
        ("fake", "cle-secrete", "fake"),
        ("cohere", None, "cohere"),
    ],
)
def test_fournisseur_effectif(provider: str, cle: str | None, attendu: str) -> None:
    parametres = Parametres(llm_provider=provider, cohere_api_key=cle)  # type: ignore[arg-type]
    assert parametres.fournisseur_effectif == attendu
    assert parametres.mode_demo is (attendu == "fake")


def test_cle_jamais_affichee_en_clair() -> None:
    parametres = Parametres(cohere_api_key=SecretStr("cle-secrete"))
    assert "cle-secrete" not in repr(parametres)


def test_liste_cors_ignore_les_espaces_et_vides() -> None:
    parametres = Parametres(cors_origines=" http://a.fr , ,http://b.fr ")
    assert parametres.liste_cors == ["http://a.fr", "http://b.fr"]
