import { Bot, Clock, Coins, Wrench } from "lucide-react";

import { useTrace } from "@/api/dossiers";
import { Badge } from "@/components/ui/badge";
import { EtatErreur } from "@/components/ui/etats";
import { Skeleton } from "@/components/ui/skeleton";
import { formaterDuree } from "@/lib/format";

function Json({ valeur }: { valeur: unknown }) {
  return (
    <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed">
      {JSON.stringify(valeur, null, 2)}
    </pre>
  );
}

/** Chronologie des appels d'outils de la dernière instruction (chargée à l'ouverture). */
export function TraceAgent({ dossierId, ouverte }: { dossierId: string; ouverte: boolean }) {
  const trace = useTrace(dossierId, ouverte);
  if (trace.isPending) {
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
      </div>
    );
  }
  if (trace.isError) return <EtatErreur erreur={trace.error} reessayer={() => trace.refetch()} />;
  const etapes = trace.data;
  if (etapes.length === 0) return <p className="text-sm text-muted-foreground">Aucune trace enregistrée.</p>;

  const duree = etapes.reduce((s, e) => s + e.duree_ms, 0);
  const jetons = etapes.reduce((s, e) => s + (e.tokens ?? 0), 0);
  const appels = etapes.filter((e) => e.outil !== "llm").length;

  return (
    <div className="space-y-4">
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1"><Wrench aria-hidden className="size-3.5" /> {appels} appels d'outils</span>
        <span className="inline-flex items-center gap-1"><Clock aria-hidden className="size-3.5" /> {formaterDuree(duree)} au total</span>
        {jetons > 0 && <span className="inline-flex items-center gap-1"><Coins aria-hidden className="size-3.5" /> {jetons.toLocaleString("fr-FR")} jetons</span>}
      </p>
      <ol className="relative space-y-1 border-l pl-6">
        {etapes.map((etape) => {
          const llm = etape.outil === "llm";
          const erreur = typeof etape.resultat === "object" && etape.resultat !== null && "erreur" in etape.resultat;
          const plan = llm && typeof etape.resultat === "object" && etape.resultat !== null
            ? (etape.resultat as { plan?: string | null }).plan
            : null;
          return (
            <li key={etape.ordre} className="relative">
              <span className="absolute -left-[31px] top-2.5 grid size-5 place-items-center rounded-full border bg-card">
                {llm ? <Bot aria-hidden className="size-3 text-primary" /> : <Wrench aria-hidden className="size-3 text-muted-foreground" />}
              </span>
              <details className="group rounded-md px-2 py-1.5 hover:bg-muted/60 open:bg-muted/40">
                <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 rounded text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <span className="w-7 shrink-0 font-mono text-xs text-muted-foreground tabular-nums">#{etape.ordre}</span>
                  <span className="font-medium">{llm ? `Réflexion de l'agent (tour ${String(etape.arguments.tour ?? "")})` : etape.outil}</span>
                  {erreur && <Badge variant="danger">erreur</Badge>}
                  <span className="ml-auto text-xs text-muted-foreground tabular-nums">
                    {formaterDuree(etape.duree_ms)}
                    {etape.tokens ? ` · ${etape.tokens} jetons` : ""}
                  </span>
                </summary>
                {plan && <p className="mt-1 text-sm text-muted-foreground">{plan}</p>}
                <div className="mt-2 grid gap-2 lg:grid-cols-2">
                  <div>
                    <p className="mb-1 text-xs font-medium">Arguments</p>
                    <Json valeur={etape.arguments} />
                  </div>
                  <div>
                    <p className="mb-1 text-xs font-medium">Résultat</p>
                    <Json valeur={etape.resultat} />
                  </div>
                </div>
              </details>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
