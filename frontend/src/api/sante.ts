import { useQuery } from "@tanstack/react-query";

import { requete } from "./client";

export type EtatComposant = { etat: "ok" | "erreur"; detail: string | null };

export type Sante = {
  statut: "ok" | "degrade";
  version: string;
  mode_demo: boolean;
  base: EtatComposant;
  redis: EtatComposant;
  fournisseur_llm: EtatComposant;
};

/** État des services, rafraîchi toutes les minutes. */
export function useSante() {
  return useQuery({
    queryKey: ["sante"],
    queryFn: () => requete<Sante>("/sante"),
    refetchInterval: 60_000,
  });
}
