/** Mots d'un nom, sans accents (même règle que le serveur : `domain/noms.py`). */
function jetons(texte: string): string[] {
  return texte
    .replace(/œ/g, "oe")
    .replace(/Œ/g, "OE")
    .replace(/æ/g, "ae")
    .replace(/Æ/g, "AE")
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .split(/[\s\-_'’.,]+/)
    .filter(Boolean);
}

/** Nom de fichier conforme au règlement, ex. `BourseExcellence2026_DUPONT.HELENE.pdf`. */
export function nomFichierAttendu(prefixe: string, nom: string, prenom: string): string {
  const nomF = jetons(nom).join("-").toUpperCase() || "NOM";
  const prenomF = jetons(prenom).join("-").toUpperCase() || "PRENOM";
  return `${prefixe}_${nomF}.${prenomF}.pdf`;
}
