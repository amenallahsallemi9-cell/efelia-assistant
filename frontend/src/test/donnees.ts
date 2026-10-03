import type { Controle, DossierDetail, ResumeReglement, Statistiques } from "@/api/types";

export const REGLEMENT: ResumeReglement = {
  edition: 2026,
  annee_universitaire: "2026-2027",
  date_limite: "2026-10-18T22:00:00Z",
  email_envoi: "EFELIA.bourses@univ-cotedazur.fr",
  prefixe_nom_fichier: "BourseExcellence2026",
  heures_ia_minimum: 24,
  cv_pages_max: 2,
  pieces_obligatoires: [],
  pieces_facultatives: [],
  laureats_max: 15,
  montant_euros: 10000,
};

export const SANTE = {
  statut: "ok",
  version: "0.1.0",
  mode_demo: false,
  base: { etat: "ok", detail: null },
  redis: { etat: "ok", detail: null },
  fournisseur_llm: { etat: "ok", detail: null },
};

export function controle(modifs: Partial<Controle> = {}): Controle {
  return {
    code: "piece_cv",
    categorie: "pieces",
    libelle: "Curriculum vitae (2 pages maximum)",
    resultat: "CONFORME",
    consequence: "A_COMPLETER",
    message: "Pièce présente (pages 2, 3).",
    preuves: [{ source: "document", page: 2, extrait: null }],
    ...modifs,
  };
}

export const DOSSIER: DossierDetail = {
  id: "11111111-1111-1111-1111-111111111111",
  statut_pipeline: "INSTRUIT",
  message_erreur: null,
  nb_pages: 3,
  created_at: "2026-10-10T08:00:00Z",
  nom_fichier_attendu: "BourseExcellence2026_DUPONT.HELENE.pdf",
  fiche: {
    nom: "Dupont",
    prenom: "Hélène",
    email: "h@etu.fr",
    formation: "M1 Informatique",
    inscrit_uca: true,
    heures_ia: 48,
    alternance: false,
    autre_bourse: false,
    autre_bourse_libelle: null,
    date_reception: "2026-10-10T08:00:00Z",
    nom_fichier: "BourseExcellence2026_DUPONT.HELENE.pdf",
  },
  pages: [
    { numero: 1, type_piece: "certificat_scolarite", methode: "texte", confiance_classification: 0.9, sensible: false },
    { numero: 2, type_piece: "cv", methode: "texte", confiance_classification: 0.9, sensible: false },
    { numero: 3, type_piece: "justificatif_social", methode: "texte", confiance_classification: 0.8, sensible: true },
  ],
  pieces: [
    {
      type: "certificat_scolarite",
      pages: [1],
      confiance: "haute",
      donnees_extraites: { nom: "DUPONT", annee_universitaire: "2026-2027", extrait: "inscrite en 2026-2027", page: 1 },
    },
    { type: "justificatif_social", pages: [3], confiance: "haute", donnees_extraites: { document_detecte: true } },
  ],
  decision: {
    id: 1,
    statut_regles: "A_COMPLETER",
    statut_propose_llm: "RECEVABLE",
    garde_fou_declenche: true,
    controles: [
      controle({ code: "eligibilite_heures_ia", categorie: "eligibilite", libelle: "Au moins 24 h d'IA", message: "48 h déclarées.", preuves: [{ source: "fiche", page: null, extrait: "Heures : 48" }] }),
      controle({
        code: "certificat_annee",
        categorie: "coherence",
        libelle: "Certificat de l'année 2026-2027",
        resultat: "NON_CONFORME",
        message: "Le certificat porte sur l'année 2025-2026.",
        preuves: [{ source: "document", page: 1, extrait: "Année universitaire 2025-2026" }],
      }),
    ],
    motifs: [],
    avertissements: [],
    conseils: [{ categorie: "cv", texte: "Ajoutez un lien GitHub.", page: 2 }],
    rapport: "# Rapport d'instruction\n\n## Verdict : À compléter\n\n- Corriger le certificat",
    modele: "fake-llm",
    created_at: "2026-10-10T08:01:00Z",
  },
  nb_decisions: 1,
};

export const STATS: Statistiques = {
  total: 3,
  par_verdict: { RECEVABLE: 1, A_COMPLETER: 1, NON_RECEVABLE: 1 },
  par_statut_pipeline: { RECU: 0, EXTRAIT: 0, CLASSE: 0, LU: 0, INDEXE: 0, INSTRUIT: 3, ERREUR: 0 },
  pieces_manquantes: [{ type: "lettre_motivation", libelle: "Lettre de motivation", nombre: 2 }],
  garde_fous_declenches: 1,
};
