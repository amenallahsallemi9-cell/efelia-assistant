"""Fournisseurs factices, déterministes et hors ligne (tests et mode démo).

- `FakeLLM` rejoue un scénario de réponses prédéfinies (tests de l'agent) ; sans
  scénario, il répond aux tâches structurées (classement, lecture) avec les
  heuristiques de `services/heuristiques.py` et, avec des outils, joue un agent
  scripté (`services/agent/demo.py`) : le mode démo est réaliste de bout en bout.
- `FakeEmbeddings` projette les mots sur 1024 dimensions par hachage : deux textes
  qui partagent du vocabulaire sont proches, sans aucun modèle.
- `FakeReranker` classe par recouvrement de vocabulaire.
"""

import json
import math
import re
import zlib
from collections.abc import Callable, Iterable, Sequence

from app.domain.modeles import TypePiece
from app.domain.noms import normaliser
from app.providers.base import (
    EmbeddingProvider,
    ErreurFournisseur,
    FormatJson,
    LLMProvider,
    Message,
    Outil,
    ReponseLLM,
    Reranker,
    UsageEmbedding,
)

DIMENSION = 1024
_PAGE = re.compile(r'<page numero="(\d+)">\n?(.*?)\n?</page>', re.DOTALL)
_DOCUMENT = re.compile(r"<document>\n?(.*?)\n?</document>", re.DOTALL)

#: Fonction de réponse personnalisée : (messages, outils, format) → réponse.
Repondeur = Callable[[Sequence[Message], Sequence[Outil], FormatJson | None], ReponseLLM]


class FakeLLM(LLMProvider):
    """LLM simulé. Enregistre chaque appel dans `appels` pour les assertions des tests."""

    nom_modele = "fake-llm"

    def __init__(
        self,
        scenario: Iterable[ReponseLLM | Exception] | None = None,
        repondeur: Repondeur | None = None,
    ) -> None:
        self._scenario = list(scenario) if scenario is not None else None
        self._repondeur = repondeur
        self.appels: list[tuple[list[Message], list[Outil], FormatJson | None]] = []

    def discuter(
        self,
        messages: Sequence[Message],
        outils: Sequence[Outil] = (),
        format_json: FormatJson | None = None,
        temperature: float = 0.0,
    ) -> ReponseLLM:
        """Réponse scénarisée, personnalisée ou heuristique."""
        self.appels.append((list(messages), list(outils), format_json))
        if self._scenario is not None:
            if not self._scenario:
                raise ErreurFournisseur("Scénario FakeLLM épuisé.")
            suivant = self._scenario.pop(0)
            if isinstance(suivant, Exception):
                raise suivant
            return suivant
        if self._repondeur is not None:
            return self._repondeur(messages, outils, format_json)
        if format_json is not None:
            return ReponseLLM(texte=json.dumps(_repondre_tache(format_json.nom, messages)))
        if outils:
            from app.services.agent.demo import repondre_agent_demo

            return repondre_agent_demo(messages)
        return ReponseLLM(texte="Réponse simulée (mode démo).")


def _dernier_message_utilisateur(messages: Sequence[Message]) -> str:
    return next((m.contenu for m in reversed(messages) if m.role == "user"), "")


def _repondre_tache(nom: str, messages: Sequence[Message]) -> dict[str, object]:
    from app.services.heuristiques import classer_par_mots_cles, lire_par_heuristique

    contenu = _dernier_message_utilisateur(messages)
    if nom == "classement_pages":
        pages = []
        for numero, texte in _PAGE.findall(contenu):
            type_piece, confiance = classer_par_mots_cles(texte)
            pages.append(
                {
                    "numero": int(numero),
                    "type_piece": type_piece.value,
                    "confiance": confiance,
                    "indice": "classement simulé (mots-clés)",
                }
            )
        return {"pages": pages}
    if nom.startswith("lecture_"):
        document = _DOCUMENT.search(contenu)
        return lire_par_heuristique(
            TypePiece(nom.removeprefix("lecture_")), document.group(1) if document else ""
        )
    raise ErreurFournisseur(f"Tâche inconnue du FakeLLM : {nom}")


# --------------------------------------------------------------------------- embeddings


def _mots(texte: str) -> list[str]:
    """Mots normalisés, réduits à 6 caractères (racinisation grossière)."""
    return [mot[:6] for mot in normaliser(texte).split() if len(mot) > 2]


class FakeEmbeddings(EmbeddingProvider):
    """Embeddings par hachage des mots (sac de mots normalisé)."""

    nom_modele = "fake-embeddings"
    dimension = DIMENSION

    def vectoriser(self, textes: Sequence[str], usage: UsageEmbedding) -> list[list[float]]:
        """Vecteurs unitaires déterministes."""
        return [self._vecteur(texte) for texte in textes]

    @staticmethod
    def _vecteur(texte: str) -> list[float]:
        vecteur = [0.0] * DIMENSION
        for mot in _mots(texte):
            empreinte = zlib.crc32(mot.encode())
            vecteur[empreinte % DIMENSION] += 1.0 if empreinte & 0x8000_0000 else -1.0
        norme = math.sqrt(sum(v * v for v in vecteur))
        if norme == 0:
            vecteur[0] = 1.0  # jamais de vecteur nul (distance cosinus indéfinie)
            return vecteur
        return [v / norme for v in vecteur]


class FakeReranker(Reranker):
    """Classement par recouvrement de vocabulaire avec la requête."""

    nom_modele = "fake-reranker"

    def reordonner(
        self, requete: str, documents: Sequence[str], top_n: int
    ) -> list[tuple[int, float]]:
        """Score = part des mots de la requête présents dans le document."""
        mots_requete = set(_mots(requete))
        scores = []
        for index, document in enumerate(documents):
            communs = mots_requete & set(_mots(document))
            scores.append((index, len(communs) / len(mots_requete) if mots_requete else 0.0))
        scores.sort(key=lambda element: (-element[1], element[0]))
        return scores[:top_n]
