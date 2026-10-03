"""Adaptateur Cohere : conversion des formats, testée avec un client simulé (sans réseau)."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.providers.base import AppelOutil, ErreurFournisseur, FormatJson, Message, Outil
from app.providers.cohere import (
    CohereEmbeddings,
    CohereLLM,
    CohereReranker,
    message_vers_cohere,
    outil_vers_cohere,
)


class ClientSimule:
    def __init__(self, reponse: Any = None, erreur: Exception | None = None) -> None:
        self.reponse = reponse
        self.erreur = erreur
        self.appels: list[dict[str, Any]] = []

    def _repondre(self, **kwargs: Any) -> Any:
        self.appels.append(kwargs)
        if self.erreur:
            raise self.erreur
        return self.reponse(kwargs) if callable(self.reponse) else self.reponse

    chat = embed = rerank = _repondre


def test_conversion_messages() -> None:
    appel = AppelOutil("c1", "lire_fiche", '{"dossier_id": "x"}')
    assert message_vers_cohere(Message("system", "règles")) == {
        "role": "system",
        "content": "règles",
    }
    assert message_vers_cohere(Message("assistant", appels_outils=(appel,), plan="je lis")) == {
        "role": "assistant",
        "tool_plan": "je lis",
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "lire_fiche", "arguments": '{"dossier_id": "x"}'},
            }
        ],
    }
    assert message_vers_cohere(Message("tool", '{"ok": true}', id_appel="c1")) == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": [{"type": "document", "document": {"data": '{"ok": true}'}}],
    }


def test_conversion_outil() -> None:
    outil = Outil("lire_fiche", "Lit la fiche", {"type": "object", "title": "X", "properties": {}})
    assert outil_vers_cohere(outil) == {
        "type": "function",
        "function": {
            "name": "lire_fiche",
            "description": "Lit la fiche",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _reponse_chat(texte: str | None = None, appels: list[Any] | None = None) -> Any:
    contenu = [SimpleNamespace(type="text", text=texte)] if texte else []
    return SimpleNamespace(
        message=SimpleNamespace(content=contenu, tool_calls=appels, tool_plan="plan"),
        usage=SimpleNamespace(tokens=SimpleNamespace(input_tokens=12.0, output_tokens=3.0)),
        finish_reason="COMPLETE",
    )


def test_chat_texte_et_format_json() -> None:
    llm = CohereLLM("cle")
    client = ClientSimule(_reponse_chat('{"a": 1}'))
    llm._client = client  # type: ignore[assignment]
    reponse = llm.discuter(
        [Message("user", "x")],
        format_json=FormatJson("t", {"type": "object", "$defs": {}, "properties": {}}),
    )
    assert reponse.texte == '{"a": 1}'
    assert reponse.tokens == 15
    assert reponse.raison_fin == "COMPLETE"
    appel = client.appels[0]
    assert appel["model"] == "command-a-03-2025"
    assert appel["temperature"] == 0.0
    assert appel["response_format"] == {
        "type": "json_object",
        "json_schema": {"type": "object", "properties": {}},
    }
    assert "tools" not in appel


def test_chat_appels_outils() -> None:
    llm = CohereLLM("cle")
    outil_appele = SimpleNamespace(
        id="t1", function=SimpleNamespace(name="verifier_format", arguments='{"dossier_id":"d"}')
    )
    llm._client = ClientSimule(_reponse_chat(None, [outil_appele]))  # type: ignore[assignment]
    reponse = llm.discuter(
        [Message("user", "x")], outils=[Outil("verifier_format", "d", {"type": "object"})]
    )
    assert reponse.texte is None
    assert reponse.plan == "plan"
    assert reponse.appels_outils == (AppelOutil("t1", "verifier_format", '{"dossier_id":"d"}'),)
    assert llm._client.appels[0]["tools"][0]["function"]["name"] == "verifier_format"  # type: ignore[attr-defined]


def test_chat_erreur_encapsulee() -> None:
    llm = CohereLLM("cle")
    llm._client = ClientSimule(erreur=TimeoutError("lent"))  # type: ignore[assignment]
    with pytest.raises(ErreurFournisseur, match="TimeoutError"):
        llm.discuter([Message("user", "x")])


def test_embeddings_par_lots() -> None:
    emb = CohereEmbeddings("cle")

    def repondre(kwargs: dict[str, Any]) -> Any:
        return SimpleNamespace(
            embeddings=SimpleNamespace(float_=[[0.1] * 1024 for _ in kwargs["texts"]])
        )

    client = ClientSimule(repondre)
    emb._client = client  # type: ignore[assignment]
    vecteurs = emb.vectoriser([f"t{i}" for i in range(200)], "requete")
    assert len(vecteurs) == 200
    assert [len(a["texts"]) for a in client.appels] == [96, 96, 8]
    assert {a["input_type"] for a in client.appels} == {"search_query"}
    assert client.appels[0]["embedding_types"] == ["float"]


def test_embeddings_nombre_incoherent() -> None:
    emb = CohereEmbeddings("cle")
    emb._client = ClientSimule(SimpleNamespace(embeddings=SimpleNamespace(float_=[])))  # type: ignore[assignment]
    with pytest.raises(ErreurFournisseur):
        emb.vectoriser(["a"], "document")


def test_rerank() -> None:
    rr = CohereReranker("cle")
    resultats = [
        SimpleNamespace(index=2, relevance_score=0.9),
        SimpleNamespace(index=0, relevance_score=0.2),
    ]
    client = ClientSimule(SimpleNamespace(results=resultats))
    rr._client = client  # type: ignore[assignment]
    assert rr.reordonner("q", ["a", "b", "c"], top_n=2) == [(2, 0.9), (0, 0.2)]
    assert client.appels[0]["model"] == "rerank-multilingual-v3.0"
    assert rr.reordonner("q", [], top_n=2) == []
