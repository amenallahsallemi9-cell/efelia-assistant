"""Normalisation et comparaison de noms de personnes et de fichiers.

Tolérances : casse, accents, ligatures (œ, æ), tirets et apostrophes des noms
composés, ordre et nombre des prénoms.
"""

import re
import unicodedata

_LIGATURES = str.maketrans({"œ": "oe", "Œ": "OE", "æ": "ae", "Æ": "AE"})
_SEPARATEURS = re.compile(r"[\s\-_'’.,]+")
_NON_ALPHANUMERIQUE = re.compile(r"[^0-9a-z]")


def sans_accents(texte: str) -> str:
    """Retire les accents et décompose les ligatures (« Élœ » → « Eloe »)."""
    decompose = unicodedata.normalize("NFKD", texte.translate(_LIGATURES))
    return "".join(c for c in decompose if not unicodedata.combining(c))


def normaliser(texte: str) -> str:
    """Forme canonique : sans accents, en minuscules, séparateurs réduits à une espace."""
    return _SEPARATEURS.sub(" ", sans_accents(texte).casefold()).strip()


def jetons(texte: str) -> tuple[str, ...]:
    """Mots d'un nom normalisé (« Jean-Pierre » → ("jean", "pierre"))."""
    return tuple(normaliser(texte).split())


def compacter(texte: str) -> str:
    """Forme compacte sans aucun séparateur (« De La Fontaine » → « delafontaine »)."""
    return _NON_ALPHANUMERIQUE.sub("", normaliser(texte))


def _prenoms_compatibles(prenoms_a: tuple[str, ...], prenoms_b: tuple[str, ...]) -> bool:
    """Vrai si l'un des ensembles de prénoms contient l'autre (ordre indifférent)."""
    if not prenoms_a or not prenoms_b:
        return False
    a, b = set(prenoms_a), set(prenoms_b)
    return a <= b or b <= a


def identite_correspond(
    nom_ref: str, prenom_ref: str, nom_doc: str | None, prenom_doc: str | None
) -> bool:
    """Compare l'identité déclarée à celle lue dans un document.

    Le nom doit être identique (après normalisation). Les prénoms peuvent être dans un
    autre ordre ou partiels (« Marie » ↔ « Marie Claire Anne »). Une inversion
    nom/prénom dans le document est tolérée.
    """
    if not nom_doc or not prenom_doc:
        return False
    nom_r, prenoms_r = compacter(nom_ref), jetons(prenom_ref)

    def _essai(nom: str, prenom: str) -> bool:
        return compacter(nom) == nom_r and _prenoms_compatibles(prenoms_r, jetons(prenom))

    return _essai(nom_doc, prenom_doc) or _essai(prenom_doc, nom_doc)


def identite_presente_dans(nom_ref: str, prenom_ref: str, texte: str) -> bool:
    """Vrai si le nom et le premier prénom figurent dans un texte libre (« Mme DUPONT Marie »)."""
    mots = set(jetons(texte))
    prenoms = jetons(prenom_ref)
    return bool(prenoms) and set(jetons(nom_ref)) <= mots and prenoms[0] in mots


def nom_fichier_attendu(prefixe: str, nom: str, prenom: str) -> str:
    """Nom de fichier conforme au règlement, ex. `BourseExcellence2026_DUPONT.MARIE.pdf`."""
    nom_f = "-".join(jetons(nom)).upper()
    prenom_f = "-".join(jetons(prenom)).upper()
    return f"{prefixe}_{nom_f}.{prenom_f}.pdf"


def nom_fichier_conforme(nom_fichier: str, prefixe: str, nom: str, prenom: str) -> bool:
    """Vérifie `PREFIXE_NOM.PRENOM[.pdf]` sans tenir compte de la casse ni des accents.

    Tolère les séparateurs internes aux noms composés (espace, tiret, apostrophe) et
    accepte le premier prénom seul ou tous les prénoms.
    """
    base = sans_accents(nom_fichier).strip()
    if base.casefold().endswith(".pdf"):
        base = base[:-4]
    motif = re.compile(
        rf"^{re.escape(sans_accents(prefixe))}_(?P<nom>.+)\.(?P<prenom>[^.]+)$", re.I
    )
    correspondance = motif.match(base)
    if not correspondance:
        return False
    prenoms = jetons(prenom)
    prenoms_acceptes = {compacter(prenom)} | ({prenoms[0]} if prenoms else set())
    return (
        compacter(correspondance["nom"]) == compacter(nom)
        and compacter(correspondance["prenom"]) in prenoms_acceptes
    )
