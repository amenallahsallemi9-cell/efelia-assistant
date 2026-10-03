import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "./App";
import { REGLEMENT, SANTE } from "./test/donnees";
import { rendre, simulerFetch } from "./test/utils";

function simuler(modeDemo = false) {
  return simulerFetch({
    "/api/sante": { corps: { ...SANTE, mode_demo: modeDemo } },
    "/api/reglement": { corps: REGLEMENT },
  });
}

describe("Mise en page", () => {
  it("affiche toujours le bandeau de non-affiliation", () => {
    simuler();
    rendre(<App />);
    expect(screen.getByText(/non affilié à EFELIA/)).toBeInTheDocument();
  });

  it("affiche le bandeau mode démo quand l'API est en mode démo", async () => {
    simuler(true);
    rendre(<App />);
    expect(await screen.findByText(/Mode démo/)).toBeInTheDocument();
  });

  it("n'affiche pas le bandeau mode démo avec un vrai fournisseur", async () => {
    const espion = simuler(false);
    rendre(<App />);
    await vi.waitFor(() => expect(espion).toHaveBeenCalled());
    expect(screen.queryByText(/Mode démo/)).not.toBeInTheDocument();
  });

  it("affiche une page 404 pour une route inconnue", () => {
    simuler();
    rendre(<App />, { route: "/nexiste-pas" });
    expect(screen.getByRole("heading", { name: "Page introuvable" })).toBeInTheDocument();
  });

  it("bascule le thème sombre au clavier", async () => {
    simuler();
    rendre(<App />);
    const bouton = screen.getByRole("button", { name: "Activer le mode sombre" });
    bouton.focus();
    await userEvent.keyboard("{Enter}");
    expect(document.documentElement).toHaveClass("dark");
    expect(screen.getByRole("button", { name: "Activer le mode clair" })).toBeInTheDocument();
    document.documentElement.classList.remove("dark");
  });

  it("propose un lien d'évitement vers le contenu", () => {
    simuler();
    rendre(<App />);
    expect(screen.getByRole("link", { name: "Aller au contenu" })).toHaveAttribute("href", "#contenu");
  });
});
