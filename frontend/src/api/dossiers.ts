import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { envoyerJson, requete } from "./client";
import type {
  DossierDetail,
  EvenementPipeline,
  FicheDepot,
  ListeDossiers,
  ReponseDepot,
  StatutPipeline,
  Statistiques,
  Trace,
  Verdict,
} from "./types";

export const STATUTS_TERMINAUX: StatutPipeline[] = ["INSTRUIT", "ERREUR"];

export type FiltresDossiers = {
  verdict?: Verdict | "";
  statut_pipeline?: StatutPipeline | "";
  recherche?: string;
  tri?: "recent" | "ancien" | "nom" | "reception" | "verdict";
  page?: number;
  taille?: number;
};

function parametres(filtres: FiltresDossiers): string {
  const p = new URLSearchParams();
  for (const [cle, valeur] of Object.entries(filtres)) {
    if (valeur !== undefined && valeur !== "") p.set(cle, String(valeur));
  }
  const texte = p.toString();
  return texte ? `?${texte}` : "";
}

export function useDossiers(filtres: FiltresDossiers) {
  return useQuery({
    queryKey: ["dossiers", filtres],
    queryFn: () => requete<ListeDossiers>(`/dossiers${parametres(filtres)}`),
    placeholderData: (precedent) => precedent,
  });
}

export function useStatistiques() {
  return useQuery({
    queryKey: ["statistiques"],
    queryFn: () => requete<Statistiques>("/dossiers/statistiques"),
  });
}

/** Détail d'un dossier ; rafraîchi tant que le traitement n'est pas terminé. */
export function useDossier(id: string) {
  return useQuery({
    queryKey: ["dossier", id],
    queryFn: () => requete<DossierDetail>(`/dossiers/${id}`),
    refetchInterval: (requeteCourante) => {
      const statut = requeteCourante.state.data?.statut_pipeline;
      return statut && !STATUTS_TERMINAUX.includes(statut) ? 4000 : false;
    },
  });
}

export function useTrace(id: string, actif: boolean) {
  return useQuery({
    queryKey: ["trace", id],
    queryFn: () => requete<Trace[]>(`/dossiers/${id}/trace`),
    enabled: actif,
  });
}

export function useDeposer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ fiche, fichier }: { fiche: FicheDepot; fichier: File }) => {
      const donnees = new FormData();
      donnees.append("fichier", fichier, fichier.name);
      donnees.append("fiche", JSON.stringify(fiche));
      donnees.append("consentement", "true");
      return requete<ReponseDepot>("/dossiers", { method: "POST", body: donnees });
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ["dossiers"] }),
  });
}

export function useRelancer(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => envoyerJson<{ message: string }>(`/dossiers/${id}/instruire`, {}),
    onSuccess: () => client.invalidateQueries({ queryKey: ["dossier", id] }),
  });
}

export function useSupprimer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => requete<null>(`/dossiers/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["dossiers"] });
      client.invalidateQueries({ queryKey: ["statistiques"] });
    },
  });
}

export type Progression = {
  statut: StatutPipeline | null;
  message: string | null;
  connecte: boolean;
};

/** Progression du pipeline en temps réel (Server-Sent Events). */
export function useProgression(id: string): Progression {
  const client = useQueryClient();
  const [etat, setEtat] = useState<Progression>({ statut: null, message: null, connecte: false });

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const source = new EventSource(`/api/dossiers/${id}/evenements`);
    source.addEventListener("progression", (evenement) => {
      const donnees = JSON.parse((evenement as MessageEvent<string>).data) as EvenementPipeline;
      setEtat({ statut: donnees.statut, message: donnees.message ?? null, connecte: true });
      if (STATUTS_TERMINAUX.includes(donnees.statut)) {
        source.close();
        client.invalidateQueries({ queryKey: ["dossier", id] });
        client.invalidateQueries({ queryKey: ["dossiers"] });
      }
    });
    source.onerror = () => setEtat((e) => ({ ...e, connecte: false }));
    return () => source.close();
  }, [id, client]);

  return etat;
}
