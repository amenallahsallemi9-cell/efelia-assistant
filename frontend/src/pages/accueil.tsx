import { ArrowRight, FileCheck2, ScanText, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { useReglement } from "@/api/reglement";
import { CompteARebours } from "@/components/accueil/compte-a-rebours";
import { VerificationRapide } from "@/components/accueil/verification-rapide";
import { variantesBouton } from "@/components/ui/button";

const ETAPES = [
  { icone: ScanText, titre: "Lecture du dossier", texte: "Texte, OCR des pages scannées et identification des pièces." },
  { icone: FileCheck2, titre: "Contrôle du règlement", texte: "Éligibilité, délai, pièces obligatoires et cohérence." },
  { icone: ShieldCheck, titre: "Verdict expliqué", texte: "Motifs, preuves avec la page citée et conseils concrets." },
];

export function PageAccueil() {
  const { data: reglement } = useReglement();
  return (
    <div className="space-y-12">
      <section className="grid gap-8 lg:grid-cols-[1.2fr_1fr] lg:items-center">
        <div className="space-y-5">
          <p className="text-sm font-medium text-primary">
            Bourse Excellence EFELIA Côte d'Azur {reglement?.edition ?? 2026}
          </p>
          <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Votre dossier <span className="whitespace-nowrap">est-il</span> complet et conforme ?
          </h1>
          <p className="max-w-prose text-muted-foreground text-pretty">
            Un agent d'IA lit votre dossier, vérifie chaque exigence du règlement et vous explique
            ce qu'il faut corriger. Il vérifie la <strong className="text-foreground">recevabilité</strong>{" "}
            : il ne prédit jamais la décision du jury.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link to="/deposer" className={variantesBouton({ size: "lg" })}>
              Déposer un dossier <ArrowRight aria-hidden />
            </Link>
            <a href="#verification" className={variantesBouton({ variant: "outline", size: "lg" })}>
              Vérifier mon éligibilité
            </a>
          </div>
        </div>
        <CompteARebours />
      </section>

      <section aria-labelledby="titre-etapes" className="space-y-4">
        <h2 id="titre-etapes" className="sr-only">
          Comment ça marche
        </h2>
        <ol className="grid gap-4 sm:grid-cols-3">
          {ETAPES.map(({ icone: Icone, titre, texte }, index) => (
            <li key={titre} className="rounded-xl border bg-card p-5 shadow-sm">
              <div className="mb-3 flex items-center gap-2">
                <span className="grid size-8 place-items-center rounded-md bg-accent text-accent-foreground">
                  <Icone aria-hidden className="size-4" />
                </span>
                <span className="text-xs font-medium text-muted-foreground">Étape {index + 1}</span>
              </div>
              <p className="font-medium">{titre}</p>
              <p className="mt-1 text-sm text-muted-foreground">{texte}</p>
            </li>
          ))}
        </ol>
      </section>

      <section id="verification" className="scroll-mt-20">
        <div className="mx-auto max-w-2xl">
          <VerificationRapide />
        </div>
      </section>
    </div>
  );
}
