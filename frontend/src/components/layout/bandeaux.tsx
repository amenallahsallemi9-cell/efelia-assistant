import { FlaskConical, Info } from "lucide-react";

import { useSante } from "@/api/sante";

/** Rappel permanent : projet étudiant indépendant, le règlement officiel fait foi. */
export function BandeauAvertissement() {
  return (
    <div className="border-b bg-muted/60 text-muted-foreground">
      <p className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2 text-xs sm:px-6">
        <Info aria-hidden className="size-3.5 shrink-0" />
        Projet étudiant indépendant, non affilié à EFELIA. Le règlement officiel fait foi.
      </p>
    </div>
  );
}

/** Affiché quand l'API tourne sans LLM réel (FakeProvider). */
export function BandeauModeDemo() {
  const { data } = useSante();
  if (!data?.mode_demo) return null;
  return (
    <div role="status" className="border-b bg-attention-fond text-attention">
      <p className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2 text-xs font-medium sm:px-6">
        <FlaskConical aria-hidden className="size-3.5 shrink-0" />
        Mode démo : les analyses sont simulées, aucun appel à un fournisseur LLM.
      </p>
    </div>
  );
}
