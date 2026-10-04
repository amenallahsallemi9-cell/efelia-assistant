"""Interfaces des fournisseurs d'IA, indépendantes de Cohere.

Le reste de l'application ne manipule que ces types : changer de fournisseur revient à
écrire une nouvelle implémentation de `LLMProvider`, `EmbeddingProvider` et `Reranker`.
"""

import json
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]
UsageEmbedding = Literal["document", "requete"]


class ErreurFournisseur(Exception):
    """Échec d'un appel au fournisseur (réseau, quota, réponse invalide)."""


@dataclass(frozen=True)
class AppelOutil:
    """Appel d'outil demandé par le LLM. `arguments` est le JSON brut renvoyé."""

    id: str
    nom: str
    arguments: str


@dataclass(frozen=True)
class Message:
    """Message de conversation, au format neutre."""

    role: Role
    contenu: str = ""
    appels_outils: tuple[AppelOutil, ...] = ()
    id_appel: str | None = None  # pour role="tool" : appel auquel on répond
    plan: str | None = None  # raisonnement annoncé avant des appels d'outils


@dataclass(frozen=True)
class Outil:
    """Outil proposé au LLM : nom, description et schéma JSON des paramètres."""

    nom: str
    description: str
    parametres: dict[str, Any]


@dataclass(frozen=True)
class FormatJson:
    """Sortie structurée attendue. `nom` identifie la tâche (journalisation, mode démo)."""

    nom: str
    schema: dict[str, Any]


@dataclass(frozen=True)
class ReponseLLM:
    """Réponse du LLM : texte final et/ou appels d'outils."""

    texte: str | None = None
    appels_outils: tuple[AppelOutil, ...] = ()
    plan: str | None = None
    tokens_entree: int | None = None
    tokens_sortie: int | None = None
    raison_fin: str | None = None
    brut: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def tokens(self) -> int | None:
        """Total des jetons consommés, si connu."""
        if self.tokens_entree is None and self.tokens_sortie is None:
            return None
        return (self.tokens_entree or 0) + (self.tokens_sortie or 0)


class LLMProvider(ABC):
    """Modèle de langage conversationnel avec appels d'outils et sortie JSON."""

    nom_modele: str

    @abstractmethod
    def discuter(
        self,
        messages: Sequence[Message],
        outils: Sequence[Outil] = (),
        format_json: FormatJson | None = None,
        temperature: float = 0.0,
    ) -> ReponseLLM:
        """Envoie la conversation et renvoie la réponse du modèle."""


class EmbeddingProvider(ABC):
    """Calcul d'embeddings normalisés."""

    nom_modele: str
    dimension: int

    @abstractmethod
    def vectoriser(self, textes: Sequence[str], usage: UsageEmbedding) -> list[list[float]]:
        """Un vecteur par texte ; `usage` distingue documents indexés et requêtes."""


class Reranker(ABC):
    """Réordonnancement de passages par pertinence."""

    nom_modele: str

    @abstractmethod
    def reordonner(
        self, requete: str, documents: Sequence[str], top_n: int
    ) -> list[tuple[int, float]]:
        """Indices des documents les plus pertinents et leur score, du meilleur au moins bon."""


#: Contraintes de validation refusées par Cohere dans `response_format` (erreur 400
#: « non-supported constraint »). Elles restent vérifiées côté serveur par Pydantic.
CONTRAINTES_VALIDATION = frozenset(
    {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
    }
)


def schema_compatible(schema: dict[str, Any], *, contraintes: bool = True) -> dict[str, Any]:
    """Schéma JSON autonome : références `$defs` remplacées, titres et défauts retirés.

    Les fournisseurs n'acceptent qu'un sous-ensemble de JSON Schema ; cette forme
    simple (sans `$ref`) est la plus largement supportée. Avec `contraintes=False`,
    les bornes (`minimum`, `maxLength`…) sont aussi retirées : la réponse doit alors
    être revalidée par le modèle Pydantic d'origine (c'est toujours le cas ici).
    """
    retires = {"$defs", "title", "default"} | (set() if contraintes else CONTRAINTES_VALIDATION)
    definitions = schema.get("$defs", {})

    def _resoudre(noeud: Any, proprietes: bool = False) -> Any:
        if isinstance(noeud, dict):
            if "$ref" in noeud and not proprietes:
                return _resoudre(definitions[noeud["$ref"].split("/")[-1]])
            # Sous `properties`, les clés sont des noms de champs (un champ peut s'appeler
            # « title » ou « minimum ») : on ne les filtre jamais.
            return {
                cle: _resoudre(valeur, proprietes=cle == "properties" and not proprietes)
                for cle, valeur in noeud.items()
                if proprietes or cle not in retires
            }
        if isinstance(noeud, list):
            return [_resoudre(element) for element in noeud]
        return noeud

    resultat: dict[str, Any] = _resoudre(schema)
    return resultat


def decoder_json(texte: str | None) -> Any:
    """Décode une réponse JSON (tolère un bloc de code Markdown autour)."""
    if not texte:
        raise ValueError("Réponse vide.")
    contenu = texte.strip()
    if contenu.startswith("```"):
        contenu = contenu.strip("`")
        contenu = contenu.removeprefix("json").strip()
    return json.loads(contenu)
