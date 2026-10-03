"""Conversion des données lues (base) en faits du domaine, pour les règles pures.

Une pièce lue avec une confiance FAIBLE ne fournit aucun fait : ses contrôles de
cohérence deviennent « indéterminés » (avertissements), jamais des non-conformités.
"""

from collections.abc import Sequence
from typing import Any

from app.db.modeles import Piece
from app.domain.coherence import (
    DonneesAttestation,
    DonneesCertificat,
    DonneesLettre,
    DonneesReleve,
    FaitsCoherence,
    ThemeLettre,
)
from app.domain.modeles import Confiance, TypePiece
from app.domain.regles import FaitsPieces


def deduire_signature(donnees: dict[str, Any]) -> bool | None:
    """Signature de l'attestation : vrai, faux, ou None si on ne peut pas trancher."""
    if donnees.get("signature_electronique"):
        return True
    marque = donnees.get("marque_visuelle")
    if marque is True:
        return True
    if marque is False:
        return None if donnees.get("mention_signature") else False
    return None


def _str(donnees: dict[str, Any], cle: str) -> str | None:
    valeur = donnees.get(cle)
    return valeur if isinstance(valeur, str) and valeur.strip() else None


def _page(donnees: dict[str, Any], piece: Piece) -> int | None:
    page = donnees.get("page")
    return page if isinstance(page, int) else (min(piece.pages) if piece.pages else None)


def construire_faits(pieces: Sequence[Piece]) -> tuple[FaitsPieces, FaitsCoherence]:
    """Faits de présence/forme (`FaitsPieces`) et de cohérence (`FaitsCoherence`)."""
    par_type = {p.type: p for p in pieces}
    fiables = {
        t: (p.donnees_extraites or {})
        for t, p in par_type.items()
        if p.confiance is not Confiance.FAIBLE
    }

    def _donnees(type_piece: TypePiece) -> dict[str, Any] | None:
        if type_piece not in par_type:
            return None
        return fiables.get(type_piece, {})

    attestation = _donnees(TypePiece.ATTESTATION_NON_CUMUL)
    cv = par_type.get(TypePiece.CV)
    faits_pieces = FaitsPieces(
        pages={t: tuple(sorted(p.pages)) for t, p in par_type.items()},
        cv_nb_pages=len(cv.pages) if cv else None,
        attestation_signee=deduire_signature(attestation) if attestation else None,
        attestation_extrait=(
            _str(attestation, "lieu_date") or _str(attestation, "extrait") if attestation else None
        ),
    )

    certificat = _donnees(TypePiece.CERTIFICAT_SCOLARITE)
    lettre = _donnees(TypePiece.LETTRE_MOTIVATION)
    releve = _donnees(TypePiece.RELEVE_NOTES)
    faits_coherence = FaitsCoherence(
        certificat=DonneesCertificat(
            nom=_str(certificat, "nom"),
            prenom=_str(certificat, "prenom"),
            etablissement=_str(certificat, "etablissement"),
            annee_universitaire=_str(certificat, "annee_universitaire"),
            page=_page(certificat, par_type[TypePiece.CERTIFICAT_SCOLARITE]),
            extrait=_str(certificat, "extrait"),
        )
        if certificat is not None
        else None,
        lettre=DonneesLettre(
            themes={
                theme: ThemeLettre(
                    present=bool(valeur.get("present")),
                    extrait=_str(valeur, "extrait"),
                    page=valeur.get("page") if isinstance(valeur.get("page"), int) else None,
                )
                for theme in ("formation", "parcours", "projet")
                if isinstance(valeur := lettre.get(theme), dict)
            },
            page=min(par_type[TypePiece.LETTRE_MOTIVATION].pages),
        )
        if lettre is not None
        else None,
        releve=DonneesReleve(
            annee=_str(releve, "annee"), page=_page(releve, par_type[TypePiece.RELEVE_NOTES])
        )
        if releve is not None
        else None,
        attestation=DonneesAttestation(
            bourse_declaree=_str(attestation, "bourse_declaree"),
            page=_page(attestation, par_type[TypePiece.ATTESTATION_NON_CUMUL]),
            extrait=_str(attestation, "extrait"),
        )
        if attestation is not None
        else None,
    )
    return faits_pieces, faits_coherence
