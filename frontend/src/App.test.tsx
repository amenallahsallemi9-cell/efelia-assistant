import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "./App";
import { rendre, simulerFetch } from "./test/utils";

const SANTE = {
  statut: "ok",
  version: "0.1.0",
  base: { etat: "ok", detail: null },
  redis: { etat: "ok", detail: null },
  fournisseur_llm: { etat: "ok", detail: null },
};

describe("Mise en page", () => {
  it("affiche toujours le bandeau de non-affiliation", () => {
    simulerFetch({ "/api/sante": { corps: { ...SANTE, mode_demo: false } } });
    rendre(<App />);
    expect(screen.getByText(/non affilié à EFELIA/)).toBeInTheDocument();
  });

  it("affiche le bandeau mode démo quand l'API est en mode démo", async () => {
    simulerFetch({ "/api/sante": { corps: { ...SANTE, mode_demo: true } } });
    rendre(<App />);
    expect(await screen.findByRole("status")).toHaveTextContent("Mode démo");
  });

  it("n'affiche pas le bandeau mode démo avec un vrai fournisseur", async () => {
    const espion = simulerFetch({ "/api/sante": { corps: { ...SANTE, mode_demo: false } } });
    rendre(<App />);
    await vi.waitFor(() => expect(espion).toHaveBeenCalled());
    expect(screen.queryByText(/Mode démo/)).not.toBeInTheDocument();
  });

  it("affiche une page 404 pour une route inconnue", () => {
    simulerFetch({ "/api/sante": { corps: { ...SANTE, mode_demo: false } } });
    rendre(<App />, { route: "/nexiste-pas" });
    expect(screen.getByRole("heading", { name: "Page introuvable" })).toBeInTheDocument();
  });

  it("bascule le thème sombre au clavier", async () => {
    simulerFetch({ "/api/sante": { corps: { ...SANTE, mode_demo: false } } });
    rendre(<App />);
    const bouton = screen.getByRole("button", { name: "Activer le mode sombre" });
    bouton.focus();
    await userEvent.keyboard("{Enter}");
    expect(document.documentElement).toHaveClass("dark");
    expect(screen.getByRole("button", { name: "Activer le mode clair" })).toBeInTheDocument();
  });
});
