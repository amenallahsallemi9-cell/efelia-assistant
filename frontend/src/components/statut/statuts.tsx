import { AlertTriangle, CheckCircle2, CircleDashed, Loader2, MinusCircle, XCircle } from "lucide-react";

import type { Resultat, StatutPipeline, Verdict } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { LIBELLES_STATUT, LIBELLES_VERDICT } from "@/lib/format";
import { cn } from "@/lib/utils";

export const STYLE_VERDICT = {
  RECEVABLE: { icone: CheckCircle2, variante: "succes", texte: "text-succes", fond: "bg-succes-fond" },
  A_COMPLETER: { icone: AlertTriangle, variante: "attention", texte: "text-attention", fond: "bg-attention-fond" },
  NON_RECEVABLE: { icone: XCircle, variante: "danger", texte: "text-danger", fond: "bg-danger-fond" },
} as const;

/** Verdict : toujours icône + libellé, jamais la couleur seule. */
export function BadgeVerdict({ verdict, className }: { verdict: Verdict | null; className?: string }) {
  if (!verdict) {
    return (
      <Badge className={className}>
        <CircleDashed aria-hidden /> En attente
      </Badge>
    );
  }
  const { icone: Icone, variante } = STYLE_VERDICT[verdict];
  return (
    <Badge variant={variante} className={className}>
      <Icone aria-hidden /> {LIBELLES_VERDICT[verdict]}
    </Badge>
  );
}

export function BadgeStatutPipeline({ statut }: { statut: StatutPipeline }) {
  if (statut === "ERREUR") {
    return (
      <Badge variant="danger">
        <XCircle aria-hidden /> Erreur
      </Badge>
    );
  }
  if (statut === "INSTRUIT") {
    return (
      <Badge>
        <CheckCircle2 aria-hidden /> Instruit
      </Badge>
    );
  }
  return (
    <Badge variant="info">
      <Loader2 aria-hidden className="animate-spin motion-reduce:animate-none" /> {LIBELLES_STATUT[statut]}
    </Badge>
  );
}

const STYLE_RESULTAT = {
  CONFORME: { icone: CheckCircle2, couleur: "text-succes", libelle: "Conforme" },
  NON_CONFORME: { icone: XCircle, couleur: "text-danger", libelle: "Non conforme" },
  INDETERMINE: { icone: AlertTriangle, couleur: "text-attention", libelle: "À vérifier" },
  NON_APPLICABLE: { icone: MinusCircle, couleur: "text-muted-foreground", libelle: "Sans objet" },
} as const;

/** ✅ ⚠️ ❌ ➖ — un avertissement non conforme s'affiche en ⚠️ (il ne bloque pas). */
export function IconeResultat({
  resultat,
  avertissement = false,
  className,
}: {
  resultat: Resultat;
  avertissement?: boolean;
  className?: string;
}) {
  const style =
    resultat === "NON_CONFORME" && avertissement ? STYLE_RESULTAT.INDETERMINE : STYLE_RESULTAT[resultat];
  const Icone = style.icone;
  return (
    <span className={cn("inline-flex", className)}>
      <Icone aria-hidden className={cn("size-4 shrink-0", style.couleur)} />
      <span className="sr-only">{avertissement && resultat === "NON_CONFORME" ? "Avertissement" : style.libelle}</span>
    </span>
  );
}
