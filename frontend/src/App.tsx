import { Route, Routes } from "react-router-dom";

import { MiseEnPage } from "@/components/layout/mise-en-page";
import { PageAVenir } from "@/pages/a-venir";
import { PageIntrouvable } from "@/pages/introuvable";

export function App() {
  return (
    <Routes>
      <Route element={<MiseEnPage />}>
        <Route index element={<PageAVenir titre="Vérification rapide" />} />
        <Route path="deposer" element={<PageAVenir titre="Déposer un dossier" />} />
        <Route path="dossiers" element={<PageAVenir titre="Tableau de bord" />} />
        <Route path="*" element={<PageIntrouvable />} />
      </Route>
    </Routes>
  );
}
