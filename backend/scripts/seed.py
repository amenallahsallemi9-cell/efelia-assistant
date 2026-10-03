"""`make seed` : charge les 5 dossiers de démonstration (remplace les précédents)."""

import sys

from app.core.config import get_parametres
from app.core.logs import configurer_logs
from app.core.reglement import get_reglement
from app.db.session import fabrique_sessions
from app.demo.jeu_de_donnees import charger_demo
from app.domain.regles import Reglement
from app.providers import construire_fournisseurs
from app.services.indexation import indexer_reglement_fichier


def main() -> int:
    """Charge le jeu de démonstration et affiche le récapitulatif."""
    parametres = get_parametres()
    configurer_logs("WARNING")
    reglement: Reglement = get_reglement()
    fournisseurs = construire_fournisseurs(parametres)
    mode = (
        "démo (FakeProvider)" if parametres.mode_demo else f"Cohere ({fournisseurs.llm.nom_modele})"
    )
    print(f"Chargement des dossiers de démonstration — fournisseur : {mode}\n")

    with fabrique_sessions()() as session:
        indexer_reglement_fichier(session, fournisseurs.embeddings, parametres.reglement_texte)
        session.commit()
        resultats = charger_demo(session, parametres, reglement, fournisseurs)

    ecarts = 0
    for r in resultats:
        ok = r.verdict is r.cas.verdict_attendu
        ecarts += not ok
        verdict = r.verdict.value if r.verdict else r.statut_pipeline.value
        nom = f"{r.cas.candidat.prenom} {r.cas.candidat.nom}"
        print(f"  {'✓' if ok else '✗'} {nom:<14} {verdict:<14} {r.cas.illustre}")
    print("\nInterface : http://localhost:3000/dossiers")
    if ecarts:
        print(f"\n{ecarts} verdict(s) inattendu(s).", file=sys.stderr)
    return 1 if ecarts else 0


if __name__ == "__main__":
    sys.exit(main())
