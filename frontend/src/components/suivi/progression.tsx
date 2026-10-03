import { Check, Loader2, XCircle } from "lucide-react";

import type { StatutPipeline } from "@/api/types";
import { ETAPES_PIPELINE } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Index de l'étape atteinte (−1 si inconnue). */
export function indexEtape(statut: StatutPipeline | null): number {
  return ETAPES_PIPELINE.findIndex((e) => e.statut === statut);
}

/**
 * Progression du pipeline : Reçu → Extrait → Classé → Lu → Indexé → Instruit.
 * `atteint` = dernière étape terminée ; en cas d'erreur, l'étape suivante est marquée en échec.
 */
export function ProgressionPipeline({
  statut,
  derniereEtapeAvantErreur,
}: {
  statut: StatutPipeline | null;
  derniereEtapeAvantErreur?: StatutPipeline | null;
}) {
  const erreur = statut === "ERREUR";
  const atteint = erreur ? indexEtape(derniereEtapeAvantErreur ?? "RECU") : indexEtape(statut);
  const total = ETAPES_PIPELINE.length;
  const pourcentage = Math.round(((atteint + 1) / total) * 100);

  return (
    <div className="space-y-6">
      <div
        role="progressbar"
        aria-label="Progression de l'analyse"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pourcentage}
        aria-valuetext={erreur ? "Analyse interrompue" : `${ETAPES_PIPELINE[Math.max(atteint, 0)].libelle}, ${pourcentage} %`}
        className="h-2 overflow-hidden rounded-full bg-muted"
      >
        <div
          className={cn("h-full rounded-full transition-[width] duration-500 motion-reduce:transition-none", erreur ? "bg-danger" : "bg-primary")}
          style={{ width: `${pourcentage}%` }}
        />
      </div>
      <ol className="grid gap-3 sm:grid-cols-6">
        {ETAPES_PIPELINE.map((etape, index) => {
          const fait = index <= atteint;
          const enCours = !erreur && index === atteint + 1;
          const echec = erreur && index === atteint + 1;
          return (
            <li key={etape.statut} className="flex items-start gap-3 sm:flex-col sm:items-center sm:text-center">
              <span
                className={cn(
                  "grid size-8 shrink-0 place-items-center rounded-full border text-xs font-medium transition-colors",
                  fait && "border-primary bg-primary text-primary-foreground",
                  enCours && "border-primary text-primary",
                  echec && "border-danger bg-danger-fond text-danger",
                  !fait && !enCours && !echec && "text-muted-foreground",
                )}
              >
                {fait ? (
                  <Check aria-hidden className="size-4" />
                ) : enCours ? (
                  <Loader2 aria-hidden className="size-4 animate-spin motion-reduce:animate-none" />
                ) : echec ? (
                  <XCircle aria-hidden className="size-4" />
                ) : (
                  index + 1
                )}
              </span>
              <div>
                <p className={cn("text-sm font-medium", !fait && !enCours && "text-muted-foreground")}>
                  {etape.libelle}
                  <span className="sr-only">
                    {fait ? " : terminé" : enCours ? " : en cours" : echec ? " : en échec" : " : à venir"}
                  </span>
                </p>
                <p className="text-xs text-muted-foreground">{etape.description}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
