import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { verifierFichier } from "@/pages/deposer";
import { DOSSIER, REGLEMENT, STATS } from "@/test/donnees";
import { FauxEventSource, rendre, simulerFetch } from "@/test/utils";

import { App } from "../App";

beforeEach(() => {
  vi.stubGlobal("EventSource", FauxEventSource);
});
afterEach(() => {
  vi.unstubAllGlobals();
  FauxEventSource.dernier = null;
});

describe("Accueil — vérification rapide", () => {
  it("envoie les réponses et affiche le résultat", async () => {
    const espion = simulerFetch({
      "/api/reglement": { corps: REGLEMENT },
      "/api/eligibilite": {
        corps: {
          eligible: false,
          dans_les_delais: true,
          date_limite: REGLEMENT.date_limite,
          message: "Au moins une condition d'éligibilité n'est pas remplie.",
          controles: [
            { code: "eligibilite_heures_ia", categorie: "eligibilite", libelle: "24 h d'IA", resultat: "NON_CONFORME", consequence: "NON_RECEVABLE", message: "20 h déclarées.", preuves: [] },
          ],
        },
      },
    });
    rendre(<App />);
    const section = document.getElementById("verification") as HTMLElement;
    const groupes = within(section).getAllByRole("group");
    await userEvent.click(within(groupes[0]).getByLabelText("Oui"));
    await userEvent.type(within(section).getByLabelText(/Heures d'enseignement/), "20");
    await userEvent.click(within(groupes[1]).getByLabelText("Non"));
    await userEvent.click(within(groupes[2]).getByLabelText("Non"));
    await userEvent.click(within(section).getByRole("button", { name: "Vérifier" }));

    expect(await screen.findByText(/n'est pas remplie/)).toBeInTheDocument();
    expect(screen.getByText("20 h déclarées.")).toBeInTheDocument();
    const appel = espion.mock.calls.find(([url]) => String(url).endsWith("/api/eligibilite"));
    expect(JSON.parse(String(appel?.[1]?.body))).toEqual({
      inscrit_uca: true, heures_ia: 20, alternance: false, autre_bourse: false, autre_bourse_libelle: null,
    });
  });
});

describe("Dépôt en trois étapes", () => {
  it("vérifie le type et la taille du fichier", () => {
    expect(verifierFichier(new File(["x"], "a.docx", { type: "application/msword" }))).toMatch(/PDF/);
    expect(verifierFichier(new File([], "a.pdf", { type: "application/pdf" }))).toMatch(/vide/);
    expect(verifierFichier(new File(["%PDF"], "a.pdf", { type: "application/pdf" }))).toBeNull();
  });

  it("guide jusqu'à l'envoi et redirige vers le suivi", async () => {
    const espion = simulerFetch({
      "/api/reglement": { corps: REGLEMENT },
      "/api/dossiers": { statut: 202, corps: { id: "abc", statut_pipeline: "RECU", nom_fichier_attendu: "x", message: "ok" } },
      "/api/dossiers/abc": { corps: { ...DOSSIER, id: "abc", statut_pipeline: "RECU", decision: null } },
    });
    rendre(<App />, { route: "/deposer" });
    const u = userEvent.setup();
    await u.type(await screen.findByLabelText("Nom"), "Dupont");
    await u.type(screen.getByLabelText("Prénom(s)"), "Hélène");
    await u.type(screen.getByLabelText("Adresse e-mail"), "h@etu.fr");
    await u.type(screen.getByLabelText(/Formation suivie/), "M1 Informatique");
    const groupes = screen.getAllByRole("group");
    await u.click(within(groupes[0]).getByLabelText("Oui"));
    await u.type(screen.getByLabelText("Heures d'enseignement en IA"), "48");
    await u.click(within(groupes[1]).getByLabelText("Non"));
    await u.click(within(groupes[2]).getByLabelText("Non"));
    await u.click(screen.getByRole("button", { name: "Continuer" }));

    // Étape 2 : nom attendu affiché, avertissement si le fichier est mal nommé
    expect(screen.getByText("BourseExcellence2026_DUPONT.HELENE.pdf")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continuer" })).toBeDisabled();
    await u.upload(screen.getByLabelText("Choisir le dossier PDF"), new File(["%PDF-1.7"], "dossier.pdf", { type: "application/pdf" }));
    expect(await screen.findByText(/ne suit pas le format attendu/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Continuer" }));

    // Étape 3 : le consentement est obligatoire
    const envoyer = screen.getByRole("button", { name: "Envoyer le dossier" });
    expect(envoyer).toBeDisabled();
    expect(screen.getByRole("link", { name: "Politique de confidentialité" })).toHaveAttribute("href", "/confidentialite");
    await u.click(screen.getByRole("checkbox"));
    await u.click(envoyer);

    expect(await screen.findByRole("heading", { name: "Analyse du dossier" })).toBeInTheDocument();
    const appel = espion.mock.calls.find(([, init]) => init?.method === "POST");
    const corps = appel?.[1]?.body as FormData;
    expect(corps.get("consentement")).toBe("true");
    expect(JSON.parse(String(corps.get("fiche")))).toMatchObject({ nom: "Dupont", heures_ia: 48, inscrit_uca: true });
    expect((corps.get("fichier") as File).name).toBe("dossier.pdf");
  });
});

describe("Suivi en temps réel", () => {
  it("avance au fil des évènements puis propose le résultat", async () => {
    simulerFetch({ [`/api/dossiers/${DOSSIER.id}`]: { corps: { ...DOSSIER, statut_pipeline: "RECU", decision: null } } });
    rendre(<App />, { route: `/dossiers/${DOSSIER.id}/suivi` });
    await waitFor(() => expect(FauxEventSource.dernier).not.toBeNull());
    const source = FauxEventSource.dernier as FauxEventSource;
    expect(source.url).toBe(`/api/dossiers/${DOSSIER.id}/evenements`);

    act(() => source.emettre({ dossier_id: DOSSIER.id, statut: "CLASSE" }));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText(/l'analyse continue/)).toBeInTheDocument();

    act(() => source.emettre({ dossier_id: DOSSIER.id, statut: "INSTRUIT" }));
    expect(screen.getByRole("link", { name: /Voir le résultat/ })).toHaveAttribute("href", `/dossiers/${DOSSIER.id}`);
    expect(source.ferme).toBe(true);
  });

  it("affiche l'erreur du pipeline", async () => {
    simulerFetch({ [`/api/dossiers/${DOSSIER.id}`]: { corps: { ...DOSSIER, statut_pipeline: "RECU", decision: null } } });
    rendre(<App />, { route: `/dossiers/${DOSSIER.id}/suivi` });
    await waitFor(() => expect(FauxEventSource.dernier).not.toBeNull());
    act(() => FauxEventSource.dernier?.emettre({ dossier_id: DOSSIER.id, statut: "ERREUR", message: "Le PDF est illisible." }));
    expect(screen.getByRole("alert")).toHaveTextContent("Le PDF est illisible.");
  });
});

describe("Détail d'un dossier", () => {
  it("affiche le verdict, le garde-fou et ouvre la preuve dans la visionneuse", async () => {
    simulerFetch({ [`/api/dossiers/${DOSSIER.id}`]: { corps: DOSSIER } });
    rendre(<App />, { route: `/dossiers/${DOSSIER.id}` });

    expect(await screen.findByRole("heading", { name: "À compléter" })).toBeInTheDocument();
    expect(screen.getByText("Garde-fou déclenché")).toBeInTheDocument();
    expect(screen.getByText(/l'agent proposait « Recevable »/i)).toBeInTheDocument();

    const image = screen.getByRole("img", { name: /Page 1 du dossier/ });
    expect(image).toHaveAttribute("src", `/api/dossiers/${DOSSIER.id}/pages/1/image`);

    await userEvent.click(screen.getByRole("button", { name: /Certificat de l'année 2026-2027 .* page 1/ }));
    expect(screen.getByRole("img", { name: /Page 1/ })).toHaveAttribute(
      "src",
      `/api/dossiers/${DOSSIER.id}/pages/1/image?surligner=Ann%C3%A9e%20universitaire%202025-2026`,
    );
    expect(screen.getByText(/Extrait surligné/)).toBeInTheDocument();
  });

  it("masque les justificatifs sensibles et rend le rapport", async () => {
    simulerFetch({ [`/api/dossiers/${DOSSIER.id}`]: { corps: DOSSIER } });
    rendre(<App />, { route: `/dossiers/${DOSSIER.id}` });
    await screen.findByRole("heading", { name: "À compléter" });
    await userEvent.selectOptions(screen.getByLabelText("Page affichée"), "3");
    expect(screen.getByText(/aperçu masqué, contenu jamais lu/)).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: "Rapport d'instruction" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /Données extraites/ }));
    expect(screen.getByText(/ni lu, ni stocké, ni transmis/)).toBeInTheDocument();
  });

  it("affiche une erreur pour un dossier inconnu", async () => {
    simulerFetch({});
    rendre(<App />, { route: "/dossiers/inconnu" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Chargement impossible");
  });
});

describe("Tableau de bord", () => {
  const LISTE = {
    total: 1,
    page: 1,
    taille: 20,
    elements: [
      {
        id: DOSSIER.id, nom: "Dupont", prenom: "Hélène", formation: "M1", date_reception: "2026-10-10T08:00:00Z",
        statut_pipeline: "INSTRUIT", verdict: "A_COMPLETER", garde_fou_declenche: true, created_at: "2026-10-10T08:00:00Z",
      },
    ],
  };

  it("affiche compteurs, dossiers et filtre par verdict", async () => {
    const espion = simulerFetch({
      "/api/dossiers/statistiques": { corps: STATS },
      "/api/dossiers": { corps: LISTE },
    });
    rendre(<App />, { route: "/dossiers" });
    expect(await screen.findByRole("link", { name: "Hélène DUPONT" })).toHaveAttribute("href", `/dossiers/${DOSSIER.id}`);
    expect(screen.getByText("Garde-fou déclenché", { selector: ".sr-only" })).toBeInTheDocument();
    expect(screen.getByText("Garde-fous déclenchés")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Filtrer par verdict"), "RECEVABLE");
    await waitFor(() =>
      expect(espion.mock.calls.some(([url]) => String(url).includes("verdict=RECEVABLE"))).toBe(true),
    );
  });

  it("propose de déposer un dossier quand la liste est vide", async () => {
    simulerFetch({
      "/api/dossiers/statistiques": { corps: { ...STATS, total: 0 } },
      "/api/dossiers": { corps: { ...LISTE, total: 0, elements: [] } },
    });
    rendre(<App />, { route: "/dossiers" });
    expect(await screen.findByText("Aucun dossier pour l'instant")).toBeInTheDocument();
  });
});
