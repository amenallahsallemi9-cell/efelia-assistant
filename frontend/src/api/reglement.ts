import { useMutation, useQuery } from "@tanstack/react-query";

import { envoyerJson, requete } from "./client";
import type { DemandeEligibilite, ReponseEligibilite, ResumeReglement } from "./types";

export function useReglement() {
  return useQuery({
    queryKey: ["reglement"],
    queryFn: () => requete<ResumeReglement>("/reglement"),
    staleTime: Infinity,
  });
}

export function useVerifierEligibilite() {
  return useMutation({
    mutationFn: (demande: DemandeEligibilite) =>
      envoyerJson<ReponseEligibilite>("/eligibilite", demande),
  });
}
