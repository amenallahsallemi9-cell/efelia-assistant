import { Link } from "react-router-dom";

import { variantesBouton } from "@/components/ui/button";

export function PageIntrouvable() {
  return (
    <div className="mx-auto max-w-md space-y-4 py-16 text-center">
      <p className="text-sm font-medium text-primary">Erreur 404</p>
      <h1 className="text-2xl font-semibold tracking-tight">Page introuvable</h1>
      <p className="text-muted-foreground">L'adresse demandée n'existe pas ou a été déplacée.</p>
      <Link to="/" className={variantesBouton({ variant: "outline" })}>
        Retour à l'accueil
      </Link>
    </div>
  );
}
