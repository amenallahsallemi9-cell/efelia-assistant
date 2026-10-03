import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { vi } from "vitest";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

/** Rendu avec routeur et client de requêtes isolés. */
export function rendre(element: ReactElement, { route = "/" }: { route?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{element}</MemoryRouter>
    </QueryClientProvider>,
  );
}

/** EventSource factice : `FauxEventSource.dernier.emettre(...)` envoie un évènement. */
export class FauxEventSource {
  static dernier: FauxEventSource | null = null;
  url: string;
  ferme = false;
  onerror: (() => void) | null = null;
  private ecouteurs = new Map<string, (e: MessageEvent<string>) => void>();

  constructor(url: string) {
    this.url = url;
    FauxEventSource.dernier = this;
  }
  addEventListener(type: string, ecouteur: (e: MessageEvent<string>) => void) {
    this.ecouteurs.set(type, ecouteur);
  }
  close() {
    this.ferme = true;
  }
  emettre(donnees: unknown) {
    this.ecouteurs.get("progression")?.(new MessageEvent("progression", { data: JSON.stringify(donnees) }));
  }
}

/**
 * Simule `fetch` : la clé est comparée au chemin (sans paramètres), ou à l'URL complète
 * si elle contient « ? ». Les routes non simulées répondent 404.
 */
export function simulerFetch(reponses: Record<string, { statut?: number; corps: unknown }>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (entree) => {
    const url = typeof entree === "string" ? entree : entree.toString();
    const chemin = url.split("?")[0];
    const cle = Object.keys(reponses).find((c) => (c.includes("?") ? url.endsWith(c) : chemin.endsWith(c)));
    if (!cle) {
      return new Response(JSON.stringify({ erreur: { code: "HTTP_404", message: "Introuvable." } }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }
    const { statut = 200, corps } = reponses[cle];
    return new Response(JSON.stringify(corps), {
      status: statut,
      headers: { "Content-Type": "application/json" },
    });
  });
}
