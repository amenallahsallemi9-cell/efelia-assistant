import { Inbox, RefreshCw, WifiOff } from "lucide-react";
import type { ReactNode } from "react";

import { ErreurApi } from "@/api/client";
import { Button } from "@/components/ui/button";

/** Liste ou contenu vide, avec une action utile. */
export function EtatVide({
  titre,
  description,
  action,
}: {
  titre: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center">
      <span className="grid size-10 place-items-center rounded-full bg-muted">
        <Inbox aria-hidden className="size-5 text-muted-foreground" />
      </span>
      <div className="space-y-1">
        <p className="font-medium">{titre}</p>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}

/** Erreur de chargement avec bouton « Réessayer ». */
export function EtatErreur({ erreur, reessayer }: { erreur: unknown; reessayer?: () => void }) {
  const message =
    erreur instanceof ErreurApi ? erreur.message : "Une erreur inattendue est survenue.";
  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center"
    >
      <span className="grid size-10 place-items-center rounded-full bg-danger-fond">
        <WifiOff aria-hidden className="size-5 text-danger" />
      </span>
      <div className="space-y-1">
        <p className="font-medium">Chargement impossible</p>
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
      {reessayer && (
        <Button variant="outline" size="sm" onClick={reessayer}>
          <RefreshCw aria-hidden /> Réessayer
        </Button>
      )}
    </div>
  );
}
