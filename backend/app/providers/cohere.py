"""Implémentation Cohere (SDK `cohere.ClientV2`)."""

import logging
from collections.abc import Sequence
from typing import Any

import cohere

from app.providers.base import (
    AppelOutil,
    EmbeddingProvider,
    ErreurFournisseur,
    FormatJson,
    LLMProvider,
    Message,
    Outil,
    ReponseLLM,
    Reranker,
    UsageEmbedding,
    schema_compatible,
)

logger = logging.getLogger(__name__)

MODELE_CHAT = "command-a-03-2025"
MODELE_EMBED = "embed-multilingual-v3.0"
MODELE_RERANK = "rerank-multilingual-v3.0"
DIMENSION_EMBED = 1024
LOT_EMBED = 96  # nombre maximal de textes par appel
TIMEOUT_SECONDES = 60


def _client(cle: str) -> cohere.ClientV2:
    return cohere.ClientV2(api_key=cle, timeout=TIMEOUT_SECONDES)


def message_vers_cohere(message: Message) -> dict[str, Any]:
    """Convertit un message neutre au format Cohere v2."""
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.id_appel,
            "content": [{"type": "document", "document": {"data": message.contenu}}],
        }
    if message.role == "assistant" and message.appels_outils:
        return {
            "role": "assistant",
            "tool_plan": message.plan or "",
            "tool_calls": [
                {
                    "id": appel.id,
                    "type": "function",
                    "function": {"name": appel.nom, "arguments": appel.arguments},
                }
                for appel in message.appels_outils
            ],
        }
    return {"role": message.role, "content": message.contenu}


def outil_vers_cohere(outil: Outil) -> dict[str, Any]:
    """Convertit une définition d'outil au format Cohere v2."""
    return {
        "type": "function",
        "function": {
            "name": outil.nom,
            "description": outil.description,
            "parameters": schema_compatible(outil.parametres),
        },
    }


class CohereLLM(LLMProvider):
    """Chat Cohere avec appels d'outils et sortie JSON."""

    def __init__(self, cle: str, modele: str = MODELE_CHAT) -> None:
        self._client = _client(cle)
        self.nom_modele = modele

    def discuter(
        self,
        messages: Sequence[Message],
        outils: Sequence[Outil] = (),
        format_json: FormatJson | None = None,
        temperature: float = 0.0,
    ) -> ReponseLLM:
        """Appel `chat` Cohere v2."""
        options: dict[str, Any] = {}
        if outils:
            options["tools"] = [outil_vers_cohere(o) for o in outils]
        if format_json is not None:
            options["response_format"] = {
                "type": "json_object",
                "json_schema": schema_compatible(format_json.schema),
            }
        try:
            reponse = self._client.chat(
                model=self.nom_modele,
                messages=[message_vers_cohere(m) for m in messages],  # type: ignore[misc]
                temperature=temperature,
                **options,
            )
        except Exception as exc:
            raise ErreurFournisseur(f"Appel Cohere échoué ({type(exc).__name__}).") from exc

        message = reponse.message
        texte = "".join(
            getattr(bloc, "text", "") for bloc in (message.content or []) if bloc.type == "text"
        )
        appels = tuple(
            AppelOutil(
                id=appel.id or f"appel_{i}",
                nom=(appel.function.name if appel.function else None) or "",
                arguments=(appel.function.arguments if appel.function else None) or "{}",
            )
            for i, appel in enumerate(message.tool_calls or [])
        )
        jetons = reponse.usage.tokens if reponse.usage else None
        return ReponseLLM(
            texte=texte or None,
            appels_outils=appels,
            plan=message.tool_plan,
            tokens_entree=int(jetons.input_tokens) if jetons and jetons.input_tokens else None,
            tokens_sortie=int(jetons.output_tokens) if jetons and jetons.output_tokens else None,
            raison_fin=str(reponse.finish_reason) if reponse.finish_reason else None,
        )


class CohereEmbeddings(EmbeddingProvider):
    """Embeddings multilingues Cohere (1024 dimensions)."""

    def __init__(self, cle: str, modele: str = MODELE_EMBED) -> None:
        self._client = _client(cle)
        self.nom_modele = modele
        self.dimension = DIMENSION_EMBED

    def vectoriser(self, textes: Sequence[str], usage: UsageEmbedding) -> list[list[float]]:
        """Appel `embed` par lots de 96 textes."""
        type_entree = "search_document" if usage == "document" else "search_query"
        vecteurs: list[list[float]] = []
        for debut in range(0, len(textes), LOT_EMBED):
            lot = list(textes[debut : debut + LOT_EMBED])
            try:
                reponse = self._client.embed(
                    model=self.nom_modele,
                    texts=lot,
                    input_type=type_entree,
                    embedding_types=["float"],
                )
            except Exception as exc:
                raise ErreurFournisseur(
                    f"Embeddings Cohere échoués ({type(exc).__name__})."
                ) from exc
            flottants = reponse.embeddings.float_ or []
            if len(flottants) != len(lot):
                raise ErreurFournisseur("Nombre d'embeddings inattendu.")
            vecteurs += [list(map(float, v)) for v in flottants]
        return vecteurs


class CohereReranker(Reranker):
    """Reranking multilingue Cohere."""

    def __init__(self, cle: str, modele: str = MODELE_RERANK) -> None:
        self._client = _client(cle)
        self.nom_modele = modele

    def reordonner(
        self, requete: str, documents: Sequence[str], top_n: int
    ) -> list[tuple[int, float]]:
        """Appel `rerank`."""
        if not documents:
            return []
        try:
            reponse = self._client.rerank(
                model=self.nom_modele, query=requete, documents=list(documents), top_n=top_n
            )
        except Exception as exc:
            raise ErreurFournisseur(f"Rerank Cohere échoué ({type(exc).__name__}).") from exc
        return [(r.index, float(r.relevance_score)) for r in reponse.results]
