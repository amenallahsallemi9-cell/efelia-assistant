"""Validation stricte et stockage des fichiers déposés."""

import stat
from pathlib import Path

import pymupdf
import pytest
from pydantic import ValidationError

from app.core.config import Parametres
from app.demo.pdf import Candidat, GenerateurDossier
from app.schemas import FicheDeclaree
from app.services.depot import ErreurDepot, nettoyer_nom_fichier, stocker_fichier, valider_pdf

CANDIDAT = Candidat("Dupont", "Hélène")


def _pdf(nb_pages: int = 1) -> bytes:
    document = pymupdf.open()
    for _ in range(nb_pages):
        document.new_page()
    return bytes(document.tobytes())


@pytest.fixture
def parametres(tmp_path: Path) -> Parametres:
    return Parametres(max_taille_mo=1, max_pages=5, stockage_dir=tmp_path)


def test_pdf_valide(parametres: Parametres) -> None:
    assert valider_pdf(_pdf(3), parametres) == 3


def test_pdf_genere_valide(parametres: Parametres) -> None:
    contenu = GenerateurDossier(CANDIDAT).certificat().cv().pdf()
    assert valider_pdf(contenu, parametres) == 3


@pytest.mark.parametrize(
    ("contenu", "code", "statut"),
    [
        (b"", "FICHIER_VIDE", 422),
        (b"PK\x03\x04 ceci est un zip", "TYPE_NON_PDF", 415),
        (b"<html>%PDF-</html>", "TYPE_NON_PDF", 415),
        (b"%PDF-1.7\n garbage sans structure", "PDF_ILLISIBLE", 422),
    ],
)
def test_contenus_refuses(parametres: Parametres, contenu: bytes, code: str, statut: int) -> None:
    with pytest.raises(ErreurDepot) as erreur:
        valider_pdf(contenu, parametres)
    assert erreur.value.code == code
    assert erreur.value.statut_http == statut


def test_fichier_trop_volumineux(parametres: Parametres) -> None:
    with pytest.raises(ErreurDepot) as erreur:
        valider_pdf(b"%PDF-" + b"0" * (1024 * 1024), parametres)
    assert erreur.value.code == "FICHIER_TROP_VOLUMINEUX"
    assert erreur.value.statut_http == 413
    assert "1 Mo" in erreur.value.message


def test_trop_de_pages(parametres: Parametres) -> None:
    with pytest.raises(ErreurDepot) as erreur:
        valider_pdf(_pdf(6), parametres)
    assert erreur.value.code == "TROP_DE_PAGES"


def test_pdf_protege(parametres: Parametres) -> None:
    document = pymupdf.open()
    document.new_page()
    chiffre = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret")
    with pytest.raises(ErreurDepot) as erreur:
        valider_pdf(chiffre, parametres)
    assert erreur.value.code == "PDF_PROTEGE"


@pytest.mark.parametrize(
    ("nom", "attendu"),
    [
        ("BourseExcellence2026_DUPONT.HELENE.pdf", "BourseExcellence2026_DUPONT.HELENE.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\moi\\dossier.pdf", "dossier.pdf"),
        ("nom\x00cache.pdf", "nomcache.pdf"),
        ("", "sans_nom.pdf"),
    ],
)
def test_nettoyer_nom_fichier(nom: str, attendu: str) -> None:
    assert nettoyer_nom_fichier(nom) == attendu


def test_stockage_nom_aleatoire_et_prive(tmp_path: Path) -> None:
    premier = stocker_fichier(b"%PDF-a", tmp_path / "stock")
    second = stocker_fichier(b"%PDF-b", tmp_path / "stock")
    assert premier != second
    assert premier.suffix == ".pdf"
    assert len(premier.stem) == 32
    assert premier.read_bytes() == b"%PDF-a"
    assert stat.S_IMODE(premier.stat().st_mode) == 0o600
    assert not list((tmp_path / "stock").glob("*.part"))


FICHE = {
    "nom": " Dupont ",
    "prenom": "Hélène",
    "email": "helene.dupont@etu.univ-cotedazur.fr",
    "formation": "M1 Informatique",
    "inscrit_uca": True,
    "heures_ia": 48,
    "alternance": False,
    "autre_bourse": False,
}


def test_fiche_valide_et_conversion() -> None:
    fiche = FicheDeclaree.model_validate(FICHE)
    assert fiche.nom == "Dupont"
    domaine = fiche.vers_domaine()
    assert domaine.heures_ia == 48
    assert domaine.autre_bourse_libelle is None


@pytest.mark.parametrize(
    "modification",
    [
        {"email": "pas-un-email"},
        {"heures_ia": -1},
        {"nom": "   "},
        {"champ_inconnu": 1},
        {"date_envoi": "2026-10-18T23:00:00"},  # sans fuseau horaire
    ],
)
def test_fiche_invalide(modification: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        FicheDeclaree.model_validate({**FICHE, **modification})
