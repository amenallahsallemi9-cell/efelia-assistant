import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

/** Rendu avec routeur et client de requêtes isolés. */
export function rendre(element: ReactElement, { route = "/" }: { route?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{element}</MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Simule une réponse JSON de `fetch`. */
export function simulerFetch(reponses: Record<string, { statut?: number; corps: unknown }>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (entree) => {
    const url = typeof entree === "string" ? entree : entree.toString();
    const cle = Object.keys(reponses).find((c) => url.endsWith(c));
    if (!cle) throw new Error(`fetch non simulé : ${url}`);
    const { statut = 200, corps } = reponses[cle];
    return new Response(JSON.stringify(corps), {
      status: statut,
      headers: { "Content-Type": "application/json" },
    });
  });
}
