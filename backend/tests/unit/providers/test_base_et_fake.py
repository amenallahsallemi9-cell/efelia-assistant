"""Interfaces neutres et fournisseurs factices (mode démo et tests)."""

import json
import math

import pytest
from pydantic import BaseModel

from app.core.config import Parametres
from app.providers import construire_fournisseurs
from app.providers.base import (
    ErreurFournisseur,
    FormatJson,
    Message,
    ReponseLLM,
    decoder_json,
    schema_compatible,
)
from app.providers.fake import FakeEmbeddings, FakeLLM, FakeReranker


class Interne(BaseModel):
    present: bool = False


class Externe(BaseModel):
    titre: str
    theme: Interne


def test_schema_compatible_sans_references() -> None:
    schema = schema_compatible(Externe.model_json_schema())
    assert "$defs" not in json.dumps(schema)
    assert "$ref" not in json.dumps(schema)
    assert "title" not in schema
    assert schema["properties"]["theme"]["properties"]["present"] == {"type": "boolean"}


@pytest.mark.parametrize(
    "texte",
    ['{"a": 1}', '```json\n{"a": 1}\n```', '```\n{"a": 1}\n```', '  {"a": 1}  '],
)
def test_decoder_json(texte: str) -> None:
    assert decoder_json(texte) == {"a": 1}


@pytest.mark.parametrize("texte", [None, "", "pas du json"])
def test_decoder_json_invalide(texte: str | None) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 (json.JSONDecodeError hérite de ValueError)
        decoder_json(texte)


def test_tokens() -> None:
    assert ReponseLLM().tokens is None
    assert ReponseLLM(tokens_entree=10, tokens_sortie=5).tokens == 15
    assert ReponseLLM(tokens_sortie=5).tokens == 5


def test_fake_llm_scenario() -> None:
    llm = FakeLLM(scenario=[ReponseLLM(texte="un"), ErreurFournisseur("panne")])
    assert llm.discuter([Message("user", "x")]).texte == "un"
    with pytest.raises(ErreurFournisseur, match="panne"):
        llm.discuter([Message("user", "y")])
    with pytest.raises(ErreurFournisseur, match="épuisé"):
        llm.discuter([Message("user", "z")])
    assert [a[0][0].contenu for a in llm.appels] == ["x", "y", "z"]


def test_fake_llm_repondeur_et_defaut() -> None:
    llm = FakeLLM(repondeur=lambda m, o, f: ReponseLLM(texte=str(len(m))))
    assert llm.discuter([Message("user", "a"), Message("user", "b")]).texte == "2"
    assert "simulée" in (FakeLLM().discuter([Message("user", "a")]).texte or "")


def test_fake_llm_classement_heuristique() -> None:
    contenu = (
        '<page numero="1">\nCERTIFICAT DE SCOLARITÉ\nest inscrit\n</page>\n'
        '<page numero="2">\nRecette de la ratatouille\n</page>'
    )
    reponse = FakeLLM().discuter(
        [Message("user", contenu)], format_json=FormatJson("classement_pages", {})
    )
    pages = decoder_json(reponse.texte)["pages"]
    assert [(p["numero"], p["type_piece"]) for p in pages] == [
        (1, "certificat_scolarite"),
        (2, "autre"),
    ]


def test_fake_llm_tache_inconnue() -> None:
    with pytest.raises(ErreurFournisseur, match="inconnue"):
        FakeLLM().discuter([Message("user", "x")], format_json=FormatJson("autre_chose", {}))


def _cosinus(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_fake_embeddings() -> None:
    emb = FakeEmbeddings()
    [a, b, c, vide] = emb.vectoriser(
        [
            "lettre de motivation et projet professionnel",
            "le projet professionnel dans la lettre de motivation",
            "relevé bancaire du mois",
            "",
        ],
        "document",
    )
    assert len(a) == 1024
    assert math.isclose(sum(v * v for v in a), 1.0)
    assert math.isclose(sum(v * v for v in vide), 1.0)
    assert _cosinus(a, b) > _cosinus(a, c)
    assert emb.vectoriser(["x y z"], "requete") == emb.vectoriser(["x y z"], "document")


def test_fake_reranker() -> None:
    documents = ["les pièces obligatoires du dossier", "date limite", "pièces du dossier"]
    resultat = FakeReranker().reordonner("quelles pièces dans le dossier", documents, top_n=2)
    assert [i for i, _ in resultat] == [0, 2]
    assert FakeReranker().reordonner("", documents, 1) == [(0, 0.0)]


def test_construire_fournisseurs_demo() -> None:
    f = construire_fournisseurs(Parametres(llm_provider="fake"))
    assert isinstance(f.llm, FakeLLM)
    assert f.embeddings.dimension == 1024


def test_construire_fournisseurs_cohere() -> None:
    from app.providers.cohere import CohereLLM

    f = construire_fournisseurs(Parametres(llm_provider="auto", cohere_api_key="cle-test"))  # type: ignore[arg-type]
    assert isinstance(f.llm, CohereLLM)
    assert f.llm.nom_modele == "command-a-03-2025"
    assert f.embeddings.nom_modele == "embed-multilingual-v3.0"
    assert f.reranker.nom_modele == "rerank-multilingual-v3.0"
    with pytest.raises(ValueError, match="COHERE_API_KEY"):
        construire_fournisseurs(Parametres(llm_provider="cohere", cohere_api_key=None))
