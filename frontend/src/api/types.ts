/** Types des réponses de l'API (miroir de backend/app/api/schemas.py). */

export type Verdict = "RECEVABLE" | "A_COMPLETER" | "NON_RECEVABLE";
export type StatutPipeline = "RECU" | "EXTRAIT" | "CLASSE" | "LU" | "INDEXE" | "INSTRUIT" | "ERREUR";
export type Resultat = "CONFORME" | "NON_CONFORME" | "INDETERMINE" | "NON_APPLICABLE";
export type Consequence = "NON_RECEVABLE" | "A_COMPLETER" | "AVERTISSEMENT";
export type TypePiece =
  | "certificat_scolarite"
  | "cv"
  | "releve_notes"
  | "lettre_motivation"
  | "attestation_non_cumul"
  | "lettre_recommandation"
  | "justificatif_social"
  | "justificatif_handicap"
  | "autre";

export type Preuve = { source: string; page: number | null; extrait: string | null };

export type Controle = {
  code: string;
  categorie: "eligibilite" | "format" | "pieces" | "coherence" | "securite";
  libelle: string;
  resultat: Resultat;
  consequence: Consequence;
  message: string;
  preuves: Preuve[];
};

export type MotifAgent = {
  source: "agent";
  message: string;
  page: number | null;
  extrait: string | null;
};

export type Motif = (Controle & { source: "regles" }) | MotifAgent;

export type Conseil = {
  categorie: "lettre" | "cv" | "pieces" | "general";
  texte: string;
  page: number | null;
  source?: string;
};

export type Decision = {
  id: number;
  statut_regles: Verdict;
  statut_propose_llm: Verdict | null;
  garde_fou_declenche: boolean;
  controles: Controle[];
  motifs: Motif[];
  avertissements: Controle[];
  conseils: Conseil[];
  rapport: string;
  modele: string;
  created_at: string;
};

export type Fiche = {
  nom: string;
  prenom: string;
  email: string;
  formation: string;
  inscrit_uca: boolean;
  heures_ia: number;
  alternance: boolean;
  autre_bourse: boolean;
  autre_bourse_libelle: string | null;
  date_reception: string;
  nom_fichier: string;
};

export type PageDossier = {
  numero: number;
  type_piece: TypePiece | null;
  methode: "texte" | "ocr";
  confiance_classification: number | null;
  sensible: boolean;
};

export type Piece = {
  type: TypePiece;
  pages: number[];
  donnees_extraites: Record<string, unknown>;
  confiance: "haute" | "moyenne" | "faible";
};

export type DossierDetail = {
  id: string;
  statut_pipeline: StatutPipeline;
  message_erreur: string | null;
  nb_pages: number | null;
  created_at: string;
  nom_fichier_attendu: string;
  fiche: Fiche;
  pages: PageDossier[];
  pieces: Piece[];
  decision: Decision | null;
  nb_decisions: number;
};

export type DossierResume = {
  id: string;
  nom: string;
  prenom: string;
  formation: string;
  date_reception: string;
  statut_pipeline: StatutPipeline;
  verdict: Verdict | null;
  garde_fou_declenche: boolean;
  created_at: string;
};

export type ListeDossiers = { elements: DossierResume[]; total: number; page: number; taille: number };

export type Statistiques = {
  total: number;
  par_verdict: Record<Verdict, number>;
  par_statut_pipeline: Record<StatutPipeline, number>;
  pieces_manquantes: { type: TypePiece; libelle: string; nombre: number }[];
  garde_fous_declenches: number;
};

export type Trace = {
  ordre: number;
  outil: string;
  arguments: Record<string, unknown>;
  resultat: unknown;
  duree_ms: number;
  tokens: number | null;
  created_at: string;
};

export type ResumeReglement = {
  edition: number;
  annee_universitaire: string;
  date_limite: string;
  email_envoi: string;
  prefixe_nom_fichier: string;
  heures_ia_minimum: number;
  cv_pages_max: number;
  pieces_obligatoires: { type: TypePiece; libelle: string }[];
  pieces_facultatives: { type: TypePiece; libelle: string }[];
  laureats_max: number;
  montant_euros: number;
};

export type DemandeEligibilite = {
  inscrit_uca: boolean;
  heures_ia: number;
  alternance: boolean;
  autre_bourse: boolean;
  autre_bourse_libelle?: string | null;
};

export type ReponseEligibilite = {
  eligible: boolean;
  dans_les_delais: boolean | null;
  controles: Controle[];
  date_limite: string;
  message: string;
};

export type FicheDepot = DemandeEligibilite & {
  nom: string;
  prenom: string;
  email: string;
  formation: string;
  date_envoi?: string | null;
};

export type ReponseDepot = {
  id: string;
  statut_pipeline: StatutPipeline;
  nom_fichier_attendu: string;
  message: string;
};

export type EvenementPipeline = {
  dossier_id: string;
  statut: StatutPipeline;
  message?: string | null;
  etape?: string;
  duree_ms?: number;
};
