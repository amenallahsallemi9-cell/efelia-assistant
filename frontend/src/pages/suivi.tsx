import { ArrowRight, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { STATUTS_TERMINAUX, useDossier, useProgression } from "@/api/dossiers";
import type { StatutPipeline } from "@/api/types";
import { ProgressionPipeline } from "@/components/suivi/progression";
import { Alerte } from "@/components/ui/alerte";
import { variantesBouton } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EtatErreur } from "@/components/ui/etats";
import { Skeleton } from "@/components/ui/skeleton";
import { LIBELLES_STATUT } from "@/lib/format";

export function PageSuivi() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const dossier = useDossier(id);
  const direct = useProgression(id);
  const derniereValide = useRef<StatutPipeline | null>(null);
  const [annonce, setAnnonce] = useState("");

  // L'évènement temps réel prime ; le détail (rafraîchi périodiquement) sert de secours.
  const statut = direct.statut ?? dossier.data?.statut_pipeline ?? null;
  const message = direct.message ?? dossier.data?.message_erreur ?? null;
  if (statut && statut !== "ERREUR") derniereValide.current = statut;
  const termine = statut === "INSTRUIT";

  useEffect(() => {
    if (statut) setAnnonce(`Étape : ${LIBELLES_STATUT[statut]}`);
    if (termine) {
      const minuteur = setTimeout(() => navigate(`/dossiers/${id}`), 1500);
      return () => clearTimeout(minuteur);
    }
  }, [statut, termine, id, navigate]);

  if (dossier.isError) return <EtatErreur erreur={dossier.error} reessayer={() => dossier.refetch()} />;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Analyse du dossier</h1>
        {dossier.data ? (
          <p className="text-muted-foreground">
            {dossier.data.fiche.prenom} {dossier.data.fiche.nom} — {dossier.data.fiche.nom_fichier}
          </p>
        ) : (
          <Skeleton className="h-5 w-64" />
        )}
      </div>
      <p className="sr-only" aria-live="polite">
        {annonce}
      </p>
      <Card>
        <CardContent className="pt-6">
          <ProgressionPipeline statut={statut} derniereEtapeAvantErreur={derniereValide.current} />
        </CardContent>
      </Card>
      {statut === "ERREUR" && (
        <Alerte variante="danger" titre="L'analyse a échoué">
          {message ?? "Une erreur est survenue."} Vous pouvez relancer l'instruction depuis la page du dossier.
        </Alerte>
      )}
      {statut && !STATUTS_TERMINAUX.includes(statut) && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 aria-hidden className="size-4 animate-spin motion-reduce:animate-none" />
          Vous pouvez quitter cette page : l'analyse continue.
        </p>
      )}
      {(termine || statut === "ERREUR") && (
        <Link to={`/dossiers/${id}`} className={variantesBouton()}>
          Voir le résultat <ArrowRight aria-hidden />
        </Link>
      )}
    </div>
  );
}
