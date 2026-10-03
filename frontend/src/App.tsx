import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";

import { MiseEnPage } from "@/components/layout/mise-en-page";
import { Skeleton } from "@/components/ui/skeleton";
import { PageAccueil } from "@/pages/accueil";
import { PageIntrouvable } from "@/pages/introuvable";

// Pages chargées à la demande : l'accueil reste léger.
const PageDeposer = lazy(() => import("@/pages/deposer").then((m) => ({ default: m.PageDeposer })));
const PageDossier = lazy(() => import("@/pages/dossier").then((m) => ({ default: m.PageDossier })));
const PageSuivi = lazy(() => import("@/pages/suivi").then((m) => ({ default: m.PageSuivi })));
const PageTableauDeBord = lazy(() =>
  import("@/pages/tableau-de-bord").then((m) => ({ default: m.PageTableauDeBord })),
);
const PageConfidentialite = lazy(() =>
  import("@/pages/confidentialite").then((m) => ({ default: m.PageConfidentialite })),
);

function Chargement() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Chargement de la page">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-64 w-full rounded-xl" />
    </div>
  );
}

export function App() {
  return (
    <Suspense fallback={<Chargement />}>
      <Routes>
        <Route element={<MiseEnPage />}>
          <Route index element={<PageAccueil />} />
          <Route path="deposer" element={<PageDeposer />} />
          <Route path="dossiers" element={<PageTableauDeBord />} />
          <Route path="dossiers/:id" element={<PageDossier />} />
          <Route path="dossiers/:id/suivi" element={<PageSuivi />} />
          <Route path="confidentialite" element={<PageConfidentialite />} />
          <Route path="*" element={<PageIntrouvable />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
