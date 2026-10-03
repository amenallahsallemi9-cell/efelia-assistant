import { Moon, Sun } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { appliquerTheme, themeCourant, type Theme } from "@/lib/theme";

export function BoutonTheme() {
  const [theme, setTheme] = useState<Theme>(themeCourant);
  const suivant: Theme = theme === "dark" ? "light" : "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={suivant === "dark" ? "Activer le mode sombre" : "Activer le mode clair"}
      onClick={() => {
        appliquerTheme(suivant);
        setTheme(suivant);
      }}
    >
      {theme === "dark" ? <Sun aria-hidden /> : <Moon aria-hidden />}
    </Button>
  );
}
