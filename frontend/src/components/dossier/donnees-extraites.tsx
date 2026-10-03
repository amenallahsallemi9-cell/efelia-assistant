import { Lock, Quote } from "lucide-react";
import type { ReactNode } from "react";

import type { Piece } from "@/api/types";
import { IconeResultat } from "@/components/statut/statuts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EtatVide } from "@/components/ui/etats";
import { LIBELLES_PIECE } from "@/lib/format";

import type { Selection } from "./selection";

const LIBELLES_CHAMPS: Record<string, string> = {
  nom: "Nom",
  prenom: "Prénom(s)",
  etablissement: "Établissement",
  formation: "Formation",
  annee_universitaire: "Année universitaire",
  annee: "Année",
  moyenne_generale: "Moyenne générale",
  mention: "Mention",
  credits_ects: "Crédits ECTS",
  competences: "Compétences",
  projets: "Projets",
  experiences: "Expériences",
  liens: "Liens",
  nb_pages: "Nombre de pages",
  nb_mots: "Nombre de mots",
  parcours: "Parcours",
  projet: "Projet",
  mentionne_ia: "Mentionne l'IA",
  mention_signature: "Mention de signature",
  lieu_date: "Fait à… le…",
  bourse_declaree: "Bourse déclarée",
  marque_visuelle: "Signature visible",
  signature_electronique: "Signature électronique",
  auteur: "Auteur",
  fonction_auteur: "Fonction",
  extrait: "Extrait",
};
const MASQUES = new Set(["page", "alertes_injection", "document_detecte"]);
const CONFIANCE = { haute: "succes", moyenne: "attention", faible: "danger" } as const;

type Theme = { present: boolean; extrait: string | null; page?: number | null };

function estTheme(valeur: unknown): valeur is Theme {
  return typeof valeur === "object" && valeur !== null && "present" in valeur;
}

function Valeur({
  cle,
  valeur,
  pageParDefaut,
  onSelectionner,
}: {
  cle: string;
  valeur: unknown;
  pageParDefaut: number;
  onSelectionner: (s: Selection) => void;
}): ReactNode {
  if (valeur === null || valeur === undefined || valeur === "") return <span className="text-muted-foreground">Non trouvé</span>;
  if (typeof valeur === "boolean") return valeur ? "Oui" : "Non";
  if (typeof valeur === "number") return valeur.toLocaleString("fr-FR");
  if (Array.isArray(valeur)) {
    if (valeur.length === 0) return <span className="text-muted-foreground">Aucun</span>;
    return (
      <ul className="flex flex-wrap gap-1.5">
        {valeur.map((element) => (
          <li key={String(element)}><Badge>{String(element)}</Badge></li>
        ))}
      </ul>
    );
  }
  if (estTheme(valeur)) {
    return (
      <span className="flex items-start gap-2">
        <IconeResultat resultat={valeur.present ? "CONFORME" : "NON_CONFORME"} avertissement className="mt-0.5" />
        {valeur.extrait ? (
          <Extrait texte={valeur.extrait} page={valeur.page ?? pageParDefaut} onSelectionner={onSelectionner} />
        ) : (
          <span className="text-muted-foreground">{valeur.present ? "Présent" : "Non abordé"}</span>
        )}
      </span>
    );
  }
  if (cle === "extrait") return <Extrait texte={String(valeur)} page={pageParDefaut} onSelectionner={onSelectionner} />;
  return String(valeur);
}

function Extrait({ texte, page, onSelectionner }: { texte: string; page: number; onSelectionner: (s: Selection) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelectionner({ page, extrait: texte })}
      className="group inline-flex items-start gap-1.5 rounded text-left italic hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Quote aria-hidden className="mt-0.5 size-3.5 shrink-0 text-muted-foreground group-hover:text-primary" />
      <span>« {texte} » <span className="not-italic text-xs text-muted-foreground">(p. {page})</span></span>
    </button>
  );
}

export function DonneesExtraites({
  pieces,
  onSelectionner,
}: {
  pieces: Piece[];
  onSelectionner: (s: Selection) => void;
}) {
  if (pieces.length === 0) return <EtatVide titre="Aucune pièce identifiée" description="Le dossier ne contient aucune pièce reconnue." />;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {pieces.map((piece) => {
        const premiere = Math.min(...piece.pages);
        const page = typeof piece.donnees_extraites.page === "number" ? piece.donnees_extraites.page : premiere;
        const sensible = piece.type === "justificatif_social" || piece.type === "justificatif_handicap";
        const champs = Object.entries(piece.donnees_extraites).filter(([cle]) => !MASQUES.has(cle));
        return (
          <Card key={piece.type}>
            <CardHeader className="pb-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="text-base">{LIBELLES_PIECE[piece.type]}</CardTitle>
                <Badge variant={CONFIANCE[piece.confiance]}>Confiance {piece.confiance}</Badge>
              </div>
              <div className="flex flex-wrap gap-1.5 text-xs">
                {piece.pages.map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => onSelectionner({ page: n, extrait: null })}
                    className="rounded-md border px-1.5 py-0.5 text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    p. {n}
                  </button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              {sensible ? (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Lock aria-hidden className="size-4" />
                  Document détecté. Son contenu n'est ni lu, ni stocké, ni transmis à l'IA (RGPD).
                </p>
              ) : champs.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucune donnée extraite.</p>
              ) : (
                <dl className="grid gap-x-4 gap-y-2.5 text-sm sm:grid-cols-[minmax(7rem,auto)_1fr]">
                  {champs.map(([cle, valeur]) => (
                    <div key={cle} className="contents">
                      <dt className="text-muted-foreground">{LIBELLES_CHAMPS[cle] ?? cle}</dt>
                      <dd className="min-w-0 break-words">
                        <Valeur cle={cle} valeur={valeur} pageParDefaut={page} onSelectionner={onSelectionner} />
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
