import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { tempsRestant } from "@/components/accueil/compte-a-rebours";
import { Checklist } from "@/components/dossier/checklist";
import { urlImage } from "@/components/dossier/visionneuse";
import { BadgeVerdict, IconeResultat } from "@/components/statut/statuts";
import { ProgressionPipeline } from "@/components/suivi/progression";
import { GraphiquePiecesManquantes } from "@/components/tableau/graphique-pieces";
import { nomFichierAttendu } from "@/lib/noms";
import { controle, STATS } from "@/test/donnees";

describe("Statuts", () => {
  it.each([
    ["RECEVABLE", "Recevable"],
    ["A_COMPLETER", "À compléter"],
    ["NON_RECEVABLE", "Non recevable"],
  ] as const)("le verdict %s porte un libellé et une icône", (verdict, libelle) => {
    const { container } = render(<BadgeVerdict verdict={verdict} />);
    expect(screen.getByText(libelle)).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("affiche « En attente » sans verdict", () => {
    render(<BadgeVerdict verdict={null} />);
    expect(screen.getByText("En attente")).toBeInTheDocument();
  });

  it("donne un équivalent textuel aux icônes de résultat", () => {
    render(
      <>
        <IconeResultat resultat="CONFORME" />
        <IconeResultat resultat="NON_CONFORME" />
        <IconeResultat resultat="NON_CONFORME" avertissement />
        <IconeResultat resultat="NON_APPLICABLE" />
      </>,
    );
    for (const texte of ["Conforme", "Non conforme", "Avertissement", "Sans objet"]) {
      expect(screen.getByText(texte)).toHaveClass("sr-only");
    }
  });
});

describe("Checklist", () => {
  const controles = [
    controle({ code: "eligibilite_alternance", categorie: "eligibilite", libelle: "Hors alternance", preuves: [{ source: "fiche", page: null, extrait: null }] }),
    controle({ code: "piece_cv", libelle: "CV", preuves: [{ source: "document", page: 2, extrait: "CV — page 1/2" }] }),
    controle({ code: "certificat_annee", categorie: "coherence", libelle: "Année", resultat: "NON_CONFORME", preuves: [{ source: "document", page: 1, extrait: "2025-2026" }] }),
  ];

  it("regroupe par catégorie et ouvre la preuve au clic", async () => {
    const choisir = vi.fn();
    render(<Checklist controles={controles} selection={null} onSelectionner={choisir} />);
    expect(screen.getByRole("heading", { name: "Éligibilité" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Cohérence" })).toBeInTheDocument();
    // Un contrôle sans page n'est pas cliquable
    expect(screen.queryByRole("button", { name: /Hors alternance/ })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Année .* afficher la page 1/ }));
    expect(choisir).toHaveBeenCalledWith({ page: 1, extrait: "2025-2026" });
  });

  it("signale le contrôle sélectionné", () => {
    render(<Checklist controles={controles} selection={{ page: 2, extrait: "CV — page 1/2" }} onSelectionner={() => {}} />);
    expect(screen.getByRole("button", { name: /^CV/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /^Année/ })).toHaveAttribute("aria-pressed", "false");
  });
});

describe("Visionneuse", () => {
  it("construit l'URL de l'aperçu avec l'extrait à surligner", () => {
    expect(urlImage("abc", { page: 3, extrait: null })).toBe("/api/dossiers/abc/pages/3/image");
    expect(urlImage("abc", { page: 1, extrait: "Année 2025-2026" })).toBe(
      "/api/dossiers/abc/pages/1/image?surligner=Ann%C3%A9e%202025-2026",
    );
  });
});

describe("Compte à rebours", () => {
  const limite = new Date("2026-10-18T22:00:00Z");

  it("calcule le temps restant", () => {
    expect(tempsRestant(limite, new Date("2026-10-16T20:58:30Z"))).toEqual({
      jours: 2, heures: 1, minutes: 1, secondes: 30, ecoule: false,
    });
  });

  it("indique l'échéance passée à la seconde près", () => {
    expect(tempsRestant(limite, new Date("2026-10-18T21:59:59Z")).ecoule).toBe(false);
    expect(tempsRestant(limite, new Date("2026-10-18T22:00:00Z")).ecoule).toBe(true);
  });
});

describe("Nom de fichier attendu", () => {
  it.each([
    ["Dupont", "Hélène", "BourseExcellence2026_DUPONT.HELENE.pdf"],
    ["De La Fontaine", "Jean-Pierre", "BourseExcellence2026_DE-LA-FONTAINE.JEAN-PIERRE.pdf"],
    ["N'Diaye", "Zoé", "BourseExcellence2026_N-DIAYE.ZOE.pdf"],
    ["Lœuvre", "Æsa", "BourseExcellence2026_LOEUVRE.AESA.pdf"],
    ["", "", "BourseExcellence2026_NOM.PRENOM.pdf"],
  ])("%s %s → %s", (nom, prenom, attendu) => {
    expect(nomFichierAttendu("BourseExcellence2026", nom, prenom)).toBe(attendu);
  });
});

describe("Progression du pipeline", () => {
  it("indique l'avancement accessible", () => {
    render(<ProgressionPipeline statut="LU" />);
    const barre = screen.getByRole("progressbar");
    expect(barre).toHaveAttribute("aria-valuenow", "67");
    expect(screen.getByText("Lu").parentElement).toHaveTextContent("terminé");
    expect(screen.getByText("Indexé").parentElement).toHaveTextContent("en cours");
  });

  it("marque l'étape en échec", () => {
    render(<ProgressionPipeline statut="ERREUR" derniereEtapeAvantErreur="EXTRAIT" />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuetext", "Analyse interrompue");
    expect(screen.getByText("Classé").parentElement).toHaveTextContent("en échec");
  });
});

describe("Graphique des pièces manquantes", () => {
  it("affiche la valeur au bout de la barre et propose une vue tableau", async () => {
    render(<GraphiquePiecesManquantes stats={STATS} />);
    const barre = screen.getByLabelText("Lettre de motivation : 2 dossiers");
    expect(within(barre).getByText("2")).toBeInTheDocument();

    await userEvent.hover(barre);
    expect(screen.getByRole("tooltip")).toHaveTextContent("2 dossiers · 67 % du total");

    await userEvent.click(screen.getByRole("button", { name: /Tableau/ }));
    const tableau = screen.getByRole("table");
    expect(within(tableau).getByRole("columnheader", { name: "Dossiers" })).toBeInTheDocument();
    expect(within(tableau).getByRole("cell", { name: "2" })).toBeInTheDocument();
  });

  it("gère l'absence de pièces manquantes", () => {
    render(<GraphiquePiecesManquantes stats={{ ...STATS, pieces_manquantes: [] }} />);
    expect(screen.getByText(/Aucune pièce manquante/)).toBeInTheDocument();
  });
});
