import { FolderOpen, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import type { Statistiques, Verdict } from "@/api/types";
import { STYLE_VERDICT } from "@/components/statut/statuts";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LIBELLES_VERDICT } from "@/lib/format";
import { cn } from "@/lib/utils";

const VERDICTS: Verdict[] = ["RECEVABLE", "A_COMPLETER", "NON_RECEVABLE"];

function Tuile({ libelle, valeur, icone, couleur }: { libelle: string; valeur: number; icone: ReactNode; couleur?: string }) {
  return (
    <Card className="p-4">
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className={cn("[&_svg]:size-4", couleur)}>{icone}</span>
        {libelle}
      </p>
      <p className="mt-2 text-3xl font-semibold tracking-tight">{valeur.toLocaleString("fr-FR")}</p>
    </Card>
  );
}

export function Tuiles({ stats }: { stats: Statistiques | undefined }) {
  if (!stats) {
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
      <Tuile libelle="Dossiers" valeur={stats.total} icone={<FolderOpen aria-hidden />} />
      {VERDICTS.map((v) => {
        const { icone: Icone, texte } = STYLE_VERDICT[v];
        return <Tuile key={v} libelle={LIBELLES_VERDICT[v]} valeur={stats.par_verdict[v]} icone={<Icone aria-hidden />} couleur={texte} />;
      })}
      <Tuile libelle="Garde-fous déclenchés" valeur={stats.garde_fous_declenches} icone={<ShieldAlert aria-hidden />} couleur="text-attention" />
    </div>
  );
}
