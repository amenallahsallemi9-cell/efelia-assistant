import { Bot, ShieldAlert } from "lucide-react";

import type { Decision, DossierDetail } from "@/api/types";
import { STYLE_VERDICT } from "@/components/statut/statuts";
import { Card } from "@/components/ui/card";
import { EXPLICATIONS_VERDICT, formaterDateHeure, LIBELLES_VERDICT } from "@/lib/format";
import { cn } from "@/lib/utils";

import { type Selection, selectionDepuisPreuves } from "./selection";

export function BandeauGardeFou({ decision }: { decision: Decision }) {
  if (!decision.garde_fou_declenche || !decision.statut_propose_llm) return null;
  return (
    <div role="status" className="flex gap-3 rounded-xl border border-attention/40 bg-attention-fond p-4 text-sm">
      <ShieldAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-attention" />
      <div className="space-y-1">
        <p className="font-semibold text-attention">Garde-fou déclenché</p>
        <p className="text-foreground/80">
          L'agent proposait « {LIBELLES_VERDICT[decision.statut_propose_llm]} ». Le statut calculé par
          les règles du règlement, « {LIBELLES_VERDICT[decision.statut_regles]} », s'applique : le LLM
          explique et conseille, il ne décide jamais seul.
        </p>
      </div>
    </div>
  );
}

export function CarteVerdict({
  dossier,
  decision,
  onSelectionner,
}: {
  dossier: DossierDetail;
  decision: Decision;
  onSelectionner: (s: Selection) => void;
}) {
  const verdict = decision.statut_regles;
  const { icone: Icone, texte, fond } = STYLE_VERDICT[verdict];
  const motifs = decision.motifs.filter((m) => m.source === "regles");

  return (
    <Card className="overflow-hidden">
      <div className={cn("flex flex-col gap-4 p-6 sm:flex-row sm:items-start", fond)}>
        <span className={cn("grid size-12 shrink-0 place-items-center rounded-full bg-card shadow-sm", texte)}>
          <Icone aria-hidden className="size-6" />
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-sm font-medium text-foreground/70">Verdict de recevabilité</p>
          <h2 className={cn("text-2xl font-semibold tracking-tight", texte)}>{LIBELLES_VERDICT[verdict]}</h2>
          <p className="text-foreground/80">{EXPLICATIONS_VERDICT[verdict]}</p>
          <p className="text-xs text-foreground/70">
            Ce verdict porte uniquement sur la recevabilité ; il ne préjuge en rien de la décision du jury.
          </p>
        </div>
      </div>
      {motifs.length > 0 && (
        <div className="border-t p-6">
          <h3 className="mb-3 text-sm font-semibold">Motifs</h3>
          <ul className="space-y-2">
            {motifs.map((motif) => {
              if (motif.source !== "regles") return null;
              const selection = selectionDepuisPreuves(motif.preuves);
              return (
                <li key={motif.code} className="text-sm">
                  <span className="font-medium">{motif.libelle}</span> — {motif.message}{" "}
                  {selection && (
                    <button
                      type="button"
                      onClick={() => onSelectionner(selection)}
                      className="text-primary underline underline-offset-4 hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                    >
                      Voir la page {selection.page}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <div className="flex flex-wrap gap-x-6 gap-y-1 border-t px-6 py-3 text-xs text-muted-foreground">
        <span>Reçu le {formaterDateHeure(dossier.fiche.date_reception)}</span>
        <span>Instruit le {formaterDateHeure(decision.created_at)}</span>
        <span className="inline-flex items-center gap-1">
          <Bot aria-hidden className="size-3.5" /> {decision.modele}
        </span>
        {dossier.nb_decisions > 1 && <span>{dossier.nb_decisions} instructions</span>}
      </div>
    </Card>
  );
}
