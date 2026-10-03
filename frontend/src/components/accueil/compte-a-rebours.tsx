import { CalendarClock } from "lucide-react";
import { useEffect, useState } from "react";

import { useReglement } from "@/api/reglement";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formaterDate } from "@/lib/format";

export type Restant = { jours: number; heures: number; minutes: number; secondes: number; ecoule: boolean };

/** Temps restant jusqu'à la date limite (borne exclusive). */
export function tempsRestant(limite: Date, maintenant: Date): Restant {
  const ms = limite.getTime() - maintenant.getTime();
  if (ms <= 0) return { jours: 0, heures: 0, minutes: 0, secondes: 0, ecoule: true };
  const s = Math.floor(ms / 1000);
  return {
    jours: Math.floor(s / 86400),
    heures: Math.floor((s % 86400) / 3600),
    minutes: Math.floor((s % 3600) / 60),
    secondes: s % 60,
    ecoule: false,
  };
}

function Unite({ valeur, libelle }: { valeur: number; libelle: string }) {
  return (
    <div className="flex min-w-14 flex-col items-center rounded-lg bg-muted px-2 py-2">
      <span className="text-2xl font-semibold tabular-nums tracking-tight">
        {String(valeur).padStart(2, "0")}
      </span>
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{libelle}</span>
    </div>
  );
}

export function CompteARebours() {
  const { data } = useReglement();
  const [maintenant, setMaintenant] = useState(() => new Date());

  useEffect(() => {
    const minuteur = setInterval(() => setMaintenant(new Date()), 1000);
    return () => clearInterval(minuteur);
  }, []);

  if (!data) return <Skeleton className="h-40 w-full rounded-xl" />;

  const limite = new Date(data.date_limite);
  // La borne est exclusive (19/10 00:00) : on affiche le dernier jour accepté.
  const dernierJour = formaterDate(new Date(limite.getTime() - 1000).toISOString());
  const restant = tempsRestant(limite, maintenant);

  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <div className="flex items-center gap-2 text-sm font-medium">
          <CalendarClock aria-hidden className="size-4 text-primary" />
          Date limite : {dernierJour} à minuit (heure de Paris)
        </div>
        {restant.ecoule ? (
          <p className="text-sm text-danger">La date limite est dépassée : un dossier envoyé maintenant ne serait pas recevable.</p>
        ) : (
          <>
            <p className="sr-only">
              Il reste {restant.jours} jours, {restant.heures} heures et {restant.minutes} minutes.
            </p>
            <div aria-hidden className="flex gap-2">
              <Unite valeur={restant.jours} libelle="jours" />
              <Unite valeur={restant.heures} libelle="heures" />
              <Unite valeur={restant.minutes} libelle="min" />
              <Unite valeur={restant.secondes} libelle="s" />
            </div>
          </>
        )}
        <p className="text-xs text-muted-foreground">
          Envoi à <span className="font-medium text-foreground">{data.email_envoi}</span>, en un seul
          PDF nommé <code className="rounded bg-muted px-1 py-0.5">{data.prefixe_nom_fichier}_NOM.PRENOM</code>.
        </p>
      </CardContent>
    </Card>
  );
}
