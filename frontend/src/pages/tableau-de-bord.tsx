import { Plus, Search } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";

import { type FiltresDossiers, useDossiers, useStatistiques } from "@/api/dossiers";
import type { StatutPipeline, Verdict } from "@/api/types";
import { GraphiquePiecesManquantes } from "@/components/tableau/graphique-pieces";
import { TableauDossiers } from "@/components/tableau/tableau-dossiers";
import { Tuiles } from "@/components/tableau/tuiles";
import { variantesBouton } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/champs";
import { EtatErreur, EtatVide } from "@/components/ui/etats";
import { LIBELLES_STATUT, LIBELLES_VERDICT } from "@/lib/format";

type Tri = NonNullable<FiltresDossiers["tri"]>;

export function PageTableauDeBord() {
  const id = useId();
  const stats = useStatistiques();
  const [saisie, setSaisie] = useState("");
  const [recherche, setRecherche] = useState("");
  const [verdict, setVerdict] = useState<Verdict | "">("");
  const [statut, setStatut] = useState<StatutPipeline | "">("");
  const [tri, setTri] = useState<Tri>("recent");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const minuteur = setTimeout(() => {
      setRecherche(saisie.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(minuteur);
  }, [saisie]);

  const liste = useDossiers({ recherche, verdict, statut_pipeline: statut, tri, page, taille: 20 });
  const filtre = Boolean(recherche || verdict || statut);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Tableau de bord</h1>
          <p className="text-muted-foreground">Suivi de la recevabilité des dossiers déposés.</p>
        </div>
        <Link to="/deposer" className={variantesBouton()}>
          <Plus aria-hidden /> Nouveau dossier
        </Link>
      </div>

      {stats.isError ? <EtatErreur erreur={stats.error} reessayer={() => stats.refetch()} /> : <Tuiles stats={stats.data} />}

      <div className="grid gap-6 2xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section aria-labelledby={`${id}-titre`} className="space-y-4">
          <h2 id={`${id}-titre`} className="sr-only">Liste des dossiers</h2>
          <div className="flex flex-wrap gap-3" role="search">
            <div className="relative min-w-56 flex-1">
              <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <label htmlFor={`${id}-recherche`} className="sr-only">Rechercher un dossier</label>
              <Input id={`${id}-recherche`} type="search" placeholder="Nom, prénom, formation…" className="pl-9" value={saisie} onChange={(e) => setSaisie(e.target.value)} />
            </div>
            <label htmlFor={`${id}-verdict`} className="sr-only">Filtrer par verdict</label>
            <Select id={`${id}-verdict`} className="w-auto" value={verdict} onChange={(e) => { setVerdict(e.target.value as Verdict | ""); setPage(1); }}>
              <option value="">Tous les verdicts</option>
              {(Object.keys(LIBELLES_VERDICT) as Verdict[]).map((v) => <option key={v} value={v}>{LIBELLES_VERDICT[v]}</option>)}
            </Select>
            <label htmlFor={`${id}-statut`} className="sr-only">Filtrer par étape</label>
            <Select id={`${id}-statut`} className="w-auto" value={statut} onChange={(e) => { setStatut(e.target.value as StatutPipeline | ""); setPage(1); }}>
              <option value="">Toutes les étapes</option>
              {(Object.keys(LIBELLES_STATUT) as StatutPipeline[]).map((s) => <option key={s} value={s}>{LIBELLES_STATUT[s]}</option>)}
            </Select>
          </div>
          {liste.isError ? (
            <EtatErreur erreur={liste.error} reessayer={() => liste.refetch()} />
          ) : liste.data && liste.data.total === 0 ? (
            filtre ? (
              <EtatVide titre="Aucun dossier ne correspond" description="Modifiez la recherche ou les filtres." />
            ) : (
              <EtatVide
                titre="Aucun dossier pour l'instant"
                description="Déposez un premier dossier, ou chargez les exemples avec « make seed »."
                action={<Link to="/deposer" className={variantesBouton({ variant: "outline", size: "sm" })}>Déposer un dossier</Link>}
              />
            )
          ) : (
            <TableauDossiers
              liste={liste.data}
              chargement={liste.isPending}
              tri={tri}
              onTrier={(t) => { setTri(t); setPage(1); }}
              page={page}
              onPage={setPage}
            />
          )}
        </section>
        <GraphiquePiecesManquantes stats={stats.data} />
      </div>
    </div>
  );
}
