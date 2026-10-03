"""Choix des fournisseurs d'IA selon la configuration (Cohere ou mode démo)."""

from dataclasses import dataclass

from app.core.config import Parametres
from app.providers.base import EmbeddingProvider, LLMProvider, Reranker


@dataclass(frozen=True)
class Fournisseurs:
    """Ensemble cohérent de fournisseurs (même famille)."""

    llm: LLMProvider
    embeddings: EmbeddingProvider
    reranker: Reranker


def construire_fournisseurs(parametres: Parametres) -> Fournisseurs:
    """Cohere si une clé est configurée (ou imposée), FakeProvider sinon."""
    if parametres.fournisseur_effectif == "cohere":
        from app.providers.cohere import CohereEmbeddings, CohereLLM, CohereReranker

        if parametres.cohere_api_key is None:
            raise ValueError("LLM_PROVIDER=cohere exige COHERE_API_KEY.")
        cle = parametres.cohere_api_key.get_secret_value()
        return Fournisseurs(CohereLLM(cle), CohereEmbeddings(cle), CohereReranker(cle))

    from app.providers.fake import FakeEmbeddings, FakeLLM, FakeReranker

    return Fournisseurs(FakeLLM(), FakeEmbeddings(), FakeReranker())
