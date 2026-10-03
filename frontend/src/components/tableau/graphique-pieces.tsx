import { Table2 } from "lucide-react";
import { useId, useState } from "react";

import type { Statistiques } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Pièces obligatoires le plus souvent manquantes : une seule série → barres horizontales
 * d'une seule couleur (validée en clair et en sombre), valeur au bout de chaque barre,
 * info-bulle au survol et au focus, vue tableau.
 */
export function GraphiquePiecesManquantes({ stats }: { stats: Statistiques | undefined }) {
  const titreId = useId();
  const [tableau, setTableau] = useState(false);
  const [survol, setSurvol] = useState<string | null>(null);

  const donnees = stats?.pieces_manquantes ?? [];
  const maximum = Math.max(1, ...donnees.map((d) => d.nombre));
  const total = stats?.total ?? 0;

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
        <div className="space-y-1.5">
          <CardTitle id={titreId} className="text-base">Pièces obligatoires manquantes</CardTitle>
          <CardDescription>Nombre de dossiers où la pièce est absente (dernière instruction).</CardDescription>
        </div>
        {donnees.length > 0 && (
          <Button variant="ghost" size="sm" aria-pressed={tableau} onClick={() => setTableau((t) => !t)}>
            <Table2 aria-hidden /> {tableau ? "Graphique" : "Tableau"}
          </Button>
        )}
      </CardHeader>
      <CardContent>
        {!stats ? (
          <div className="space-y-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-6 w-full" />)}</div>
        ) : donnees.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Aucune pièce manquante pour l'instant.</p>
        ) : tableau ? (
          <table className="w-full text-sm" aria-labelledby={titreId}>
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th scope="col" className="py-2 font-medium">Pièce</th>
                <th scope="col" className="py-2 text-right font-medium">Dossiers</th>
              </tr>
            </thead>
            <tbody>
              {donnees.map((d) => (
                <tr key={d.type} className="border-b last:border-0">
                  <td className="py-2">{d.libelle}</td>
                  <td className="py-2 text-right tabular-nums">{d.nombre}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <ul aria-labelledby={titreId} className="space-y-3">
            {donnees.map((d) => {
              const largeur = (d.nombre / maximum) * 100;
              const part = total ? Math.round((d.nombre / total) * 100) : 0;
              return (
                <li
                  key={d.type}
                  tabIndex={0}
                  onMouseEnter={() => setSurvol(d.type)}
                  onMouseLeave={() => setSurvol(null)}
                  onFocus={() => setSurvol(d.type)}
                  onBlur={() => setSurvol(null)}
                  className="group relative rounded-md p-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={`${d.libelle} : ${d.nombre} dossier${d.nombre > 1 ? "s" : ""}`}
                >
                  <p className="mb-1 truncate text-sm">{d.libelle}</p>
                  <div className="flex items-center gap-2">
                    <div className="h-4 flex-1">
                      <div
                        className="h-full rounded-r-[4px] transition-[width] duration-300 motion-reduce:transition-none"
                        style={{ width: `${largeur}%`, backgroundColor: "var(--graphique)" }}
                      />
                    </div>
                    <span className="w-8 text-right text-sm font-medium tabular-nums">{d.nombre}</span>
                  </div>
                  {survol === d.type && (
                    <div role="tooltip" className="pointer-events-none absolute right-0 -top-9 z-10 rounded-md border bg-popover px-2.5 py-1.5 text-xs shadow-md">
                      <span className="font-medium">{d.nombre}</span> dossier{d.nombre > 1 ? "s" : ""} · {part} % du total
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
