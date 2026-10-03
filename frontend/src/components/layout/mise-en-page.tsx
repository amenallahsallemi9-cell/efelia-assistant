import { GraduationCap } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/lib/utils";

import { BandeauAvertissement, BandeauModeDemo } from "./bandeaux";
import { BoutonTheme } from "./bouton-theme";

const LIENS = [
  { vers: "/", libelle: "Vérification rapide" },
  { vers: "/deposer", libelle: "Déposer un dossier" },
  { vers: "/dossiers", libelle: "Tableau de bord" },
];

export function MiseEnPage() {
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#contenu"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-4 focus:py-2 focus:shadow"
      >
        Aller au contenu
      </a>
      <BandeauAvertissement />
      <BandeauModeDemo />
      <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="grid size-7 place-items-center rounded-md bg-primary text-primary-foreground">
              <GraduationCap aria-hidden className="size-4" />
            </span>
            <span>
              EFELIA <span className="font-normal text-muted-foreground">Instruction</span>
            </span>
          </NavLink>
          <nav aria-label="Navigation principale" className="ml-auto flex items-center gap-1 overflow-x-auto">
            {LIENS.map((lien) => (
              <NavLink
                key={lien.vers}
                to={lien.vers}
                end={lien.vers === "/"}
                className={({ isActive }) =>
                  cn(
                    "whitespace-nowrap rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground",
                    isActive && "bg-secondary text-foreground",
                  )
                }
              >
                {lien.libelle}
              </NavLink>
            ))}
          </nav>
          <BoutonTheme />
        </div>
      </header>
      <main id="contenu" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
        <Outlet />
      </main>
      <footer className="border-t py-6 text-center text-xs text-muted-foreground">
        Bourse Excellence EFELIA Côte d'Azur 2026 · L'outil vérifie la recevabilité, il ne prédit
        pas la décision du jury.
      </footer>
    </div>
  );
}
