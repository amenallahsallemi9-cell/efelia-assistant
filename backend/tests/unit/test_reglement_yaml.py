"""Le fichier `config/regles_2026.yaml` est complet, valide et fidèle au règlement."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml

from app.core import reglement as module_reglement
from app.core.reglement import ErreurReglement, charger_reglement
from app.domain.modeles import TypePiece
from app.domain.regles import Consequence

CHEMIN = Path(__file__).resolve().parents[3] / "config" / "regles_2026.yaml"


@pytest.fixture
def contenu() -> dict:  # type: ignore[type-arg]
    return yaml.safe_load(CHEMIN.read_text(encoding="utf-8"))


def _ecrire(tmp_path: Path, contenu: object) -> Path:
    chemin = tmp_path / "regles.yaml"
    chemin.write_text(yaml.safe_dump(contenu, allow_unicode=True), encoding="utf-8")
    return chemin


def test_valeurs_du_reglement_2026() -> None:
    r = charger_reglement(CHEMIN)
    assert r.edition == 2026
    assert r.annee_universitaire == "2026-2027"
    assert r.heures_ia_minimum == 24
    assert r.alternance_autorisee is False
    assert r.prefixe_nom_fichier == "BourseExcellence2026"
    assert r.email_envoi == "EFELIA.bourses@univ-cotedazur.fr"
    assert r.reception_avant == datetime(2026, 10, 19, tzinfo=ZoneInfo("Europe/Paris"))
    assert r.cv_pages_max == 2
    assert r.lettre_themes == ("formation", "parcours", "projet")
    assert len(r.pieces_obligatoires) == 5
    assert {p.type for p in r.pieces_facultatives} == {
        TypePiece.LETTRE_RECOMMANDATION,
        TypePiece.JUSTIFICATIF_SOCIAL,
        TypePiece.JUSTIFICATIF_HANDICAP,
    }
    assert r.selection.laureats_max == 15
    assert r.selection.montant_euros == 10_000
    assert r.selection.reconduction_automatique is False


def test_consequences_validees_par_l_utilisateur() -> None:
    r = charger_reglement(CHEMIN)
    assert r.consequence("format_nom_fichier") is Consequence.AVERTISSEMENT
    assert r.consequence("format_delai") is Consequence.NON_RECEVABLE
    assert r.consequence("piece_manquante") is Consequence.A_COMPLETER
    assert r.consequence("lettre_themes") is Consequence.AVERTISSEMENT
    for code in ("inscription_uca", "heures_ia", "alternance", "autre_bourse"):
        assert r.consequence(f"eligibilite_{code}") is Consequence.NON_RECEVABLE


def test_libelle_piece() -> None:
    r = charger_reglement(CHEMIN)
    assert r.libelle_piece(TypePiece.CV).startswith("Curriculum vitae")
    assert r.libelle_piece(TypePiece.AUTRE) == "autre"


def test_consequence_inconnue() -> None:
    with pytest.raises(KeyError, match="non configurée"):
        charger_reglement(CHEMIN).consequence("inexistant")


def test_fichier_introuvable(tmp_path: Path) -> None:
    with pytest.raises(ErreurReglement, match="introuvable"):
        charger_reglement(tmp_path / "absent.yaml")


def test_yaml_invalide(tmp_path: Path) -> None:
    chemin = tmp_path / "regles.yaml"
    chemin.write_text("edition: [2026", encoding="utf-8")
    with pytest.raises(ErreurReglement, match="YAML invalide"):
        charger_reglement(chemin)


def test_consequence_manquante(tmp_path: Path, contenu: dict) -> None:  # type: ignore[type-arg]
    del contenu["consequences"]["format_delai"]
    with pytest.raises(ErreurReglement, match="format_delai"):
        charger_reglement(_ecrire(tmp_path, contenu))


def test_code_inconnu(tmp_path: Path, contenu: dict) -> None:  # type: ignore[type-arg]
    contenu["consequences"]["regle_inventee"] = "A_COMPLETER"
    with pytest.raises(ErreurReglement, match="regle_inventee"):
        charger_reglement(_ecrire(tmp_path, contenu))


def test_champ_inconnu_refuse(tmp_path: Path, contenu: dict) -> None:  # type: ignore[type-arg]
    contenu["eligibilite"]["age_maximum"] = 30
    with pytest.raises(ErreurReglement):
        charger_reglement(_ecrire(tmp_path, contenu))


def test_type_piece_inconnu(tmp_path: Path, contenu: dict) -> None:  # type: ignore[type-arg]
    contenu["pieces_obligatoires"].append({"type": "photo", "libelle": "Photo"})
    with pytest.raises(ErreurReglement):
        charger_reglement(_ecrire(tmp_path, contenu))


def test_date_avec_fuseau_refusee(tmp_path: Path, contenu: dict) -> None:  # type: ignore[type-arg]
    contenu["format"]["reception_avant"] = "2026-10-19T00:00:00+02:00"
    with pytest.raises(ErreurReglement, match="heure locale"):
        charger_reglement(_ecrire(tmp_path, contenu))


def test_fuseau_inconnu(tmp_path: Path, contenu: dict) -> None:  # type: ignore[type-arg]
    contenu["format"]["fuseau"] = "Europe/Atlantide"
    with pytest.raises(ErreurReglement, match="Fuseau"):
        charger_reglement(_ecrire(tmp_path, contenu))


def test_get_reglement_utilise_les_parametres(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import Parametres

    module_reglement.get_reglement.cache_clear()
    monkeypatch.setattr(
        module_reglement, "get_parametres", lambda: Parametres(regles_fichier=CHEMIN)
    )
    assert module_reglement.get_reglement().edition == 2026
    module_reglement.get_reglement.cache_clear()
