import { ChevronRight } from "lucide-react";

import type { Controle } from "@/api/types";
import { IconeResultat } from "@/components/statut/statuts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LIBELLES_CATEGORIE } from "@/lib/format";
import { cn } from "@/lib/utils";

import { type Selection, selectionDepuisPreuves } from "./selection";

const ORDRE = ["eligibilite", "format", "pieces", "coherence"] as const;

export function LigneControle({
  controle,
  selection,
  onSelectionner,
}: {
  controle: Controle;
  selection: Selection | null;
  onSelectionner: (s: Selection) => void;
}) {
  const cible = selectionDepuisPreuves(controle.preuves);
  const active = cible !== null && selection?.page === cible.page && selection.extrait === cible.extrait;
  const contenu = (
    <>
      <IconeResultat
        resultat={controle.resultat}
        avertissement={controle.consequence === "AVERTISSEMENT"}
        className="mt-0.5"
      />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{controle.libelle}</span>
        <span className="block text-sm text-muted-foreground">{controle.message}</span>
      </span>
      {cible && (
        <span className="flex shrink-0 items-center gap-0.5 text-xs text-muted-foreground">
          p. {cible.page} <ChevronRight aria-hidden className="size-3.5" />
        </span>
      )}
    </>
  );
  if (!cible) return <li className="flex gap-3 px-3 py-2.5">{contenu}</li>;
  return (
    <li>
      <button
        type="button"
        aria-pressed={active}
        aria-label={`${controle.libelle} : ${controle.message} — afficher la page ${cible.page}`}
        onClick={() => onSelectionner(cible)}
        className={cn(
          "flex w-full gap-3 rounded-md px-3 py-2.5 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          active && "bg-accent hover:bg-accent",
        )}
      >
        {contenu}
      </button>
    </li>
  );
}

export function Checklist({
  controles,
  selection,
  onSelectionner,
}: {
  controles: Controle[];
  selection: Selection | null;
  onSelectionner: (s: Selection) => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Pièces et critères</CardTitle>
        <p className="text-xs text-muted-foreground">
          Cliquez sur un contrôle pour afficher sa preuve dans le document.
        </p>
      </CardHeader>
      <CardContent className="space-y-4 px-3">
        {ORDRE.map((categorie) => {
          const groupe = controles.filter((c) => c.categorie === categorie);
          if (groupe.length === 0) return null;
          return (
            <section key={categorie} aria-labelledby={`categorie-${categorie}`}>
              <h3 id={`categorie-${categorie}`} className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {LIBELLES_CATEGORIE[categorie]}
              </h3>
              <ul className="space-y-0.5">
                {groupe.map((c) => (
                  <LigneControle key={c.code} controle={c} selection={selection} onSelectionner={onSelectionner} />
                ))}
              </ul>
            </section>
          );
        })}
        <p className="flex flex-wrap gap-x-4 gap-y-1 px-3 pt-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1"><IconeResultat resultat="CONFORME" /> Conforme</span>
          <span className="inline-flex items-center gap-1"><IconeResultat resultat="INDETERMINE" /> À vérifier / avertissement</span>
          <span className="inline-flex items-center gap-1"><IconeResultat resultat="NON_CONFORME" /> Non conforme</span>
          <span className="inline-flex items-center gap-1"><IconeResultat resultat="NON_APPLICABLE" /> Sans objet</span>
        </p>
      </CardContent>
    </Card>
  );
}
