import { ArrowLeft, FileSearch, Lightbulb, ListChecks, ScrollText, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { STATUTS_TERMINAUX, useDossier, useProgression } from "@/api/dossiers";
import type { Conseil, Controle } from "@/api/types";
import { ActionsDossier } from "@/components/dossier/actions";
import { BandeauGardeFou, CarteVerdict } from "@/components/dossier/carte-verdict";
import { Checklist, LigneControle } from "@/components/dossier/checklist";
import { DonneesExtraites } from "@/components/dossier/donnees-extraites";
import { Rapport } from "@/components/dossier/rapport";
import type { Selection } from "@/components/dossier/selection";
import { TraceAgent } from "@/components/dossier/trace-agent";
import { Visionneuse } from "@/components/dossier/visionneuse";
import { BadgeStatutPipeline } from "@/components/statut/statuts";
import { ProgressionPipeline } from "@/components/suivi/progression";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Alerte } from "@/components/ui/alerte";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EtatErreur, EtatVide } from "@/components/ui/etats";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const CATEGORIES_CONSEIL: Record<Conseil["categorie"], string> = {
  lettre: "Lettre de motivation",
  cv: "CV",
  pieces: "Pièces",
  general: "Général",
};

function SqueletteDossier() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Chargement du dossier">
      <Skeleton className="h-8 w-72" />
      <Skeleton className="h-44 w-full rounded-xl" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-96 rounded-xl" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
    </div>
  );
}

function PointsDeVigilance({
  avertissements,
  selection,
  onSelectionner,
}: {
  avertissements: Controle[];
  selection: Selection | null;
  onSelectionner: (s: Selection) => void;
}) {
  if (avertissements.length === 0) return null;
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldAlert aria-hidden className="size-4 text-attention" /> Points de vigilance
        </CardTitle>
      </CardHeader>
      <CardContent className="px-3">
        <ul className="space-y-0.5">
          {avertissements.map((a, i) => (
            <LigneControle key={`${a.code}-${i}`} controle={a} selection={selection} onSelectionner={onSelectionner} />
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export function PageDossier() {
  const { id = "" } = useParams();
  const dossier = useDossier(id);
  const direct = useProgression(id);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [traceOuverte, setTraceOuverte] = useState(false);

  if (dossier.isPending) return <SqueletteDossier />;
  if (dossier.isError) return <EtatErreur erreur={dossier.error} reessayer={() => dossier.refetch()} />;

  const d = dossier.data;
  const decision = d.decision;
  const statut = direct.statut ?? d.statut_pipeline;
  const termine = STATUTS_TERMINAUX.includes(statut);
  const pageAffichee: Selection = selection ?? { page: 1, extrait: null };
  const choisir = (s: Selection) => {
    setSelection(s);
    if (window.matchMedia?.("(max-width: 1023px)").matches) {
      document.getElementById("visionneuse")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };
  const coherence = decision?.controles.filter((c) => c.categorie === "coherence") ?? [];

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <Link to="/dossiers" className="inline-flex items-center gap-1 rounded text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <ArrowLeft aria-hidden className="size-4" /> Tableau de bord
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              {d.fiche.prenom} {d.fiche.nom.toUpperCase()}
            </h1>
            <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              {d.fiche.formation} · {d.fiche.heures_ia} h d'IA · {d.nb_pages ?? "?"} pages
              <BadgeStatutPipeline statut={statut} />
            </p>
          </div>
          <ActionsDossier dossierId={d.id} peutRelancer={termine} />
        </div>
      </div>

      {!termine && (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <p className="text-sm font-medium">Analyse en cours…</p>
            <ProgressionPipeline statut={statut} />
          </CardContent>
        </Card>
      )}
      {statut === "ERREUR" && (
        <Alerte variante="danger" titre="L'analyse a échoué">
          {d.message_erreur ?? "Erreur inconnue."} Utilisez « Relancer l'instruction ».
        </Alerte>
      )}

      {decision ? (
        <>
          <BandeauGardeFou decision={decision} />
          <CarteVerdict dossier={d} decision={decision} onSelectionner={choisir} />
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
            <div className="space-y-6">
              <Checklist controles={decision.controles} selection={selection} onSelectionner={choisir} />
              <PointsDeVigilance
                avertissements={decision.avertissements.filter((a) => a.categorie === "securite")}
                selection={selection}
                onSelectionner={choisir}
              />
            </div>
            <div id="visionneuse" className="scroll-mt-20 lg:sticky lg:top-20 lg:self-start">
              <Visionneuse dossierId={d.id} pages={d.pages} selection={pageAffichee} onSelectionner={setSelection} />
            </div>
          </div>

          <Tabs defaultValue="rapport">
            <TabsList aria-label="Détails de l'instruction">
              <TabsTrigger value="rapport"><ScrollText aria-hidden /> Rapport</TabsTrigger>
              <TabsTrigger value="donnees"><FileSearch aria-hidden /> Données extraites</TabsTrigger>
              <TabsTrigger value="coherence"><ListChecks aria-hidden /> Cohérence</TabsTrigger>
              <TabsTrigger value="conseils"><Lightbulb aria-hidden /> Conseils</TabsTrigger>
            </TabsList>
            <TabsContent value="rapport">
              <Card><CardContent className="pt-6"><Rapport markdown={decision.rapport} /></CardContent></Card>
            </TabsContent>
            <TabsContent value="donnees">
              <DonneesExtraites pieces={d.pieces} onSelectionner={choisir} />
            </TabsContent>
            <TabsContent value="coherence">
              <Card>
                <CardContent className="px-3 pt-4">
                  {coherence.length === 0 ? (
                    <EtatVide titre="Aucun contrôle de cohérence" description="Les pièces nécessaires n'ont pas été trouvées." />
                  ) : (
                    <ul className="space-y-0.5">
                      {coherence.map((c) => (
                        <LigneControle key={c.code} controle={c} selection={selection} onSelectionner={choisir} />
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="conseils">
              {decision.conseils.length === 0 ? (
                <EtatVide titre="Aucun conseil" description="L'agent n'a formulé aucun conseil pour ce dossier." />
              ) : (
                <ul className="grid gap-3 md:grid-cols-2">
                  {decision.conseils.map((conseil, i) => (
                    <li key={i} className="rounded-xl border bg-card p-4 text-sm shadow-sm">
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {CATEGORIES_CONSEIL[conseil.categorie] ?? conseil.categorie}
                      </p>
                      <p>{conseil.texte}</p>
                      {conseil.page && (
                        <button
                          type="button"
                          onClick={() => choisir({ page: conseil.page as number, extrait: null })}
                          className="mt-2 rounded text-xs text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          Voir la page {conseil.page}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>
          </Tabs>

          <Card>
            <CardContent className="px-6 py-0">
              <Accordion type="single" collapsible onValueChange={(v) => setTraceOuverte(v === "trace")}>
                <AccordionItem value="trace">
                  <AccordionTrigger>Trace de l'agent (journal d'audit)</AccordionTrigger>
                  <AccordionContent>
                    <TraceAgent dossierId={d.id} ouverte={traceOuverte} />
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </CardContent>
          </Card>
        </>
      ) : (
        termine && statut !== "ERREUR" && <EtatVide titre="Aucune décision" description="Relancez l'instruction pour obtenir un verdict." />
      )}
    </div>
  );
}
