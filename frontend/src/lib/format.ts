import type { StatutPipeline, TypePiece, Verdict } from "@/api/types";

const DATE_HEURE = new Intl.DateTimeFormat("fr-FR", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Europe/Paris",
});
const DATE = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeZone: "Europe/Paris" });

/** « 10 oct. 2026, 10:00 » (heure de Paris). */
export function formaterDateHeure(iso: string): string {
  return DATE_HEURE.format(new Date(iso));
}

/** « 18 octobre 2026 » (heure de Paris). */
export function formaterDate(iso: string): string {
  return DATE.format(new Date(iso));
}

/** Durée lisible : « 850 ms », « 2,4 s ». */
export function formaterDuree(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} s`;
}

export const LIBELLES_VERDICT: Record<Verdict, string> = {
  RECEVABLE: "Recevable",
  A_COMPLETER: "À compléter",
  NON_RECEVABLE: "Non recevable",
};

export const EXPLICATIONS_VERDICT: Record<Verdict, string> = {
  RECEVABLE: "Le dossier est complet et conforme : il peut être examiné par le jury.",
  A_COMPLETER: "Le dossier doit être complété ou corrigé avant d'être examiné.",
  NON_RECEVABLE: "Le dossier ne remplit pas une condition d'éligibilité ou de délai.",
};

export const ETAPES_PIPELINE: { statut: StatutPipeline; libelle: string; description: string }[] = [
  { statut: "RECU", libelle: "Reçu", description: "Fichier validé et enregistré" },
  { statut: "EXTRAIT", libelle: "Extrait", description: "Texte lu, OCR des pages scannées" },
  { statut: "CLASSE", libelle: "Classé", description: "Chaque page associée à une pièce" },
  { statut: "LU", libelle: "Lu", description: "Informations extraites de chaque pièce" },
  { statut: "INDEXE", libelle: "Indexé", description: "Recherche sémantique prête" },
  { statut: "INSTRUIT", libelle: "Instruit", description: "Verdict, motifs et conseils" },
];

export const LIBELLES_STATUT: Record<StatutPipeline, string> = {
  RECU: "Reçu",
  EXTRAIT: "Extrait",
  CLASSE: "Classé",
  LU: "Lu",
  INDEXE: "Indexé",
  INSTRUIT: "Instruit",
  ERREUR: "Erreur",
};

export const LIBELLES_PIECE: Record<TypePiece, string> = {
  certificat_scolarite: "Certificat de scolarité",
  cv: "Curriculum vitae",
  releve_notes: "Relevé de notes",
  lettre_motivation: "Lettre de motivation",
  attestation_non_cumul: "Attestation de non-cumul",
  lettre_recommandation: "Lettre de recommandation",
  justificatif_social: "Justificatif social",
  justificatif_handicap: "Justificatif de handicap",
  autre: "Autre document",
};

export const LIBELLES_CATEGORIE: Record<string, string> = {
  eligibilite: "Éligibilité",
  format: "Format",
  pieces: "Pièces",
  coherence: "Cohérence",
  securite: "Sécurité",
};
