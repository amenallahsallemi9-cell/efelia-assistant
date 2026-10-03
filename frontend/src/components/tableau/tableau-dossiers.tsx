import { ArrowDown, ChevronLeft, ChevronRight, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

import type { FiltresDossiers } from "@/api/dossiers";
import type { ListeDossiers } from "@/api/types";
import { BadgeStatutPipeline, BadgeVerdict } from "@/components/statut/statuts";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formaterDateHeure } from "@/lib/format";

type Tri = NonNullable<FiltresDossiers["tri"]>;

function EnTete({ libelle, tri, actuel, onTrier }: { libelle: string; tri?: Tri; actuel: Tri; onTrier: (t: Tri) => void }) {
  if (!tri) return <th scope="col" className="px-4 py-3 font-medium">{libelle}</th>;
  const actif = actuel === tri;
  return (
    <th scope="col" aria-sort={actif ? "ascending" : "none"} className="px-4 py-3 font-medium">
      <button
        type="button"
        onClick={() => onTrier(tri)}
        className="inline-flex items-center gap-1 rounded hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {libelle}
        <ArrowDown aria-hidden className={actif ? "size-3.5 text-foreground" : "size-3.5 opacity-30"} />
        <span className="sr-only">{actif ? "(tri actif)" : "(trier)"}</span>
      </button>
    </th>
  );
}

export function TableauDossiers({
  liste,
  chargement,
  tri,
  onTrier,
  page,
  onPage,
}: {
  liste: ListeDossiers | undefined;
  chargement: boolean;
  tri: Tri;
  onTrier: (t: Tri) => void;
  page: number;
  onPage: (p: number) => void;
}) {
  const pages = liste ? Math.max(1, Math.ceil(liste.total / liste.taille)) : 1;
  return (
    <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <caption className="sr-only">Dossiers déposés</caption>
          <thead className="border-b bg-muted/50 text-muted-foreground">
            <tr>
              <EnTete libelle="Candidat·e" tri="nom" actuel={tri} onTrier={onTrier} />
              <EnTete libelle="Formation" actuel={tri} onTrier={onTrier} />
              <EnTete libelle="Reçu le" tri="reception" actuel={tri} onTrier={onTrier} />
              <EnTete libelle="Étape" actuel={tri} onTrier={onTrier} />
              <EnTete libelle="Verdict" tri="verdict" actuel={tri} onTrier={onTrier} />
            </tr>
          </thead>
          <tbody>
            {chargement && !liste
              ? [0, 1, 2, 3].map((i) => (
                  <tr key={i} className="border-b last:border-0">
                    {[0, 1, 2, 3, 4].map((j) => <td key={j} className="px-4 py-3"><Skeleton className="h-4 w-full" /></td>)}
                  </tr>
                ))
              : liste?.elements.map((d) => (
                  <tr key={d.id} className="border-b transition-colors last:border-0 hover:bg-muted/40">
                    <td className="whitespace-nowrap px-4 py-3">
                      <Link to={`/dossiers/${d.id}`} className="rounded font-medium hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                        {d.prenom} {d.nom.toUpperCase()}
                      </Link>
                    </td>
                    <td className="max-w-64 truncate px-4 py-3 text-muted-foreground">{d.formation}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-muted-foreground tabular-nums">{formaterDateHeure(d.date_reception)}</td>
                    <td className="px-4 py-3"><BadgeStatutPipeline statut={d.statut_pipeline} /></td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-2">
                        <BadgeVerdict verdict={d.verdict} />
                        {d.garde_fou_declenche && (
                          <span title="Garde-fou déclenché" className="text-attention">
                            <ShieldAlert aria-hidden className="size-4" />
                            <span className="sr-only">Garde-fou déclenché</span>
                          </span>
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
      {liste && liste.total > liste.taille && (
        <nav aria-label="Pagination" className="flex items-center justify-between border-t px-4 py-2 text-sm">
          <span className="text-muted-foreground">
            Page {page} sur {pages} · {liste.total} dossiers
          </span>
          <div className="flex gap-1">
            <Button variant="ghost" size="icon" aria-label="Page précédente" disabled={page <= 1} onClick={() => onPage(page - 1)}>
              <ChevronLeft aria-hidden />
            </Button>
            <Button variant="ghost" size="icon" aria-label="Page suivante" disabled={page >= pages} onClick={() => onPage(page + 1)}>
              <ChevronRight aria-hidden />
            </Button>
          </div>
        </nav>
      )}
    </div>
  );
}
