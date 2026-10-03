import { Check, FileText, Loader2, UploadCloud, X } from "lucide-react";
import { type ComponentProps, type DragEvent, type FormEvent, useId, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErreurApi } from "@/api/client";
import { useDeposer } from "@/api/dossiers";
import { useReglement } from "@/api/reglement";
import type { FicheDepot } from "@/api/types";
import { Alerte } from "@/components/ui/alerte";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AideChamp, Checkbox, Input, Label } from "@/components/ui/champs";
import { ChoixOuiNon } from "@/components/ui/choix";
import { nomFichierAttendu } from "@/lib/noms";
import { cn } from "@/lib/utils";

const TAILLE_MAX_MO = 20;
const ETAPES = ["Informations", "Dossier PDF", "Confirmation"];

type Formulaire = {
  nom: string;
  prenom: string;
  email: string;
  formation: string;
  inscrit_uca: boolean | null;
  heures_ia: string;
  alternance: boolean | null;
  autre_bourse: boolean | null;
  autre_bourse_libelle: string;
  date_envoi: string;
};

const VIDE: Formulaire = {
  nom: "",
  prenom: "",
  email: "",
  formation: "",
  inscrit_uca: null,
  heures_ia: "",
  alternance: null,
  autre_bourse: null,
  autre_bourse_libelle: "",
  date_envoi: "",
};

/** Vérifications côté navigateur ; le serveur revalide tout (type réel, taille, pages). */
export function verifierFichier(fichier: File): string | null {
  const estPdf = fichier.type === "application/pdf" || fichier.name.toLowerCase().endsWith(".pdf");
  if (!estPdf) return "Le dossier doit être un fichier PDF.";
  if (fichier.size > TAILLE_MAX_MO * 1024 * 1024) return `Le fichier dépasse ${TAILLE_MAX_MO} Mo.`;
  if (fichier.size === 0) return "Le fichier est vide.";
  return null;
}

function Indicateur({ etape }: { etape: number }) {
  return (
    <ol className="flex items-center gap-2 text-sm" aria-label="Étapes du dépôt">
      {ETAPES.map((libelle, index) => {
        const faite = index < etape;
        const courante = index === etape;
        return (
          <li key={libelle} className="flex items-center gap-2" aria-current={courante ? "step" : undefined}>
            <span
              className={cn(
                "grid size-6 place-items-center rounded-full border text-xs font-medium",
                faite && "border-primary bg-primary text-primary-foreground",
                courante && "border-primary text-primary",
                !faite && !courante && "text-muted-foreground",
              )}
            >
              {faite ? <Check aria-hidden className="size-3.5" /> : index + 1}
            </span>
            <span className={cn("hidden sm:inline", courante ? "font-medium" : "text-muted-foreground")}>
              {libelle}
              {faite && <span className="sr-only"> (terminée)</span>}
            </span>
            {index < ETAPES.length - 1 && <span aria-hidden className="h-px w-6 bg-border sm:w-10" />}
          </li>
        );
      })}
    </ol>
  );
}

function Champ({
  id,
  libelle,
  aide,
  ...props
}: { id: string; libelle: string; aide?: string } & ComponentProps<typeof Input>) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{libelle}</Label>
      <Input id={id} aria-describedby={aide ? `${id}-aide` : undefined} {...props} />
      {aide && <AideChamp id={`${id}-aide`}>{aide}</AideChamp>}
    </div>
  );
}

export function PageDeposer() {
  const navigate = useNavigate();
  const { data: reglement } = useReglement();
  const deposer = useDeposer();
  const id = useId();
  const entreeFichier = useRef<HTMLInputElement>(null);
  const [etape, setEtape] = useState(0);
  const [form, setForm] = useState<Formulaire>(VIDE);
  const [fichier, setFichier] = useState<File | null>(null);
  const [erreurFichier, setErreurFichier] = useState<string | null>(null);
  const [survol, setSurvol] = useState(false);
  const [consentement, setConsentement] = useState(false);

  const maj = <K extends keyof Formulaire>(cle: K, valeur: Formulaire[K]) =>
    setForm((f) => ({ ...f, [cle]: valeur }));
  const attendu = nomFichierAttendu(reglement?.prefixe_nom_fichier ?? "BourseExcellence2026", form.nom, form.prenom);
  const nomConforme =
    fichier && fichier.name.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase() ===
      attendu.toLowerCase();

  const choisir = (f: File | undefined) => {
    if (!f) return;
    const erreur = verifierFichier(f);
    setErreurFichier(erreur);
    setFichier(erreur ? null : f);
  };

  const deposerFichier = (evenement: DragEvent) => {
    evenement.preventDefault();
    setSurvol(false);
    choisir(evenement.dataTransfer.files[0]);
  };

  const suivant = (evenement: FormEvent) => {
    evenement.preventDefault();
    setEtape((e) => e + 1);
  };

  const envoyer = (evenement: FormEvent) => {
    evenement.preventDefault();
    if (!fichier || !consentement) return;
    const fiche: FicheDepot = {
      nom: form.nom.trim(),
      prenom: form.prenom.trim(),
      email: form.email.trim(),
      formation: form.formation.trim(),
      inscrit_uca: form.inscrit_uca === true,
      heures_ia: Number(form.heures_ia),
      alternance: form.alternance === true,
      autre_bourse: form.autre_bourse === true,
      autre_bourse_libelle: form.autre_bourse ? form.autre_bourse_libelle.trim() || null : null,
      date_envoi: form.date_envoi ? new Date(form.date_envoi).toISOString() : null,
    };
    deposer.mutate(
      { fiche, fichier },
      { onSuccess: (reponse) => navigate(`/dossiers/${reponse.id}/suivi`) },
    );
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Déposer un dossier</h1>
        <p className="text-muted-foreground">
          Le dossier est analysé en une à deux minutes. Vous pourrez le supprimer à tout moment.
        </p>
      </div>
      <Indicateur etape={etape} />

      {etape === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Vos informations</CardTitle>
            <CardDescription>Telles qu'elles figurent sur votre certificat de scolarité.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={suivant} className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2">
                <Champ id={`${id}-nom`} libelle="Nom" required autoComplete="family-name" value={form.nom} onChange={(e) => maj("nom", e.target.value)} />
                <Champ id={`${id}-prenom`} libelle="Prénom(s)" required autoComplete="given-name" value={form.prenom} onChange={(e) => maj("prenom", e.target.value)} />
              </div>
              <Champ id={`${id}-email`} libelle="Adresse e-mail" type="email" required autoComplete="email" value={form.email} onChange={(e) => maj("email", e.target.value)} />
              <Champ id={`${id}-formation`} libelle="Formation suivie en 2026-2027" required placeholder="Ex. : Master 1 Informatique, parcours IA" value={form.formation} onChange={(e) => maj("formation", e.target.value)} />
              <ChoixOuiNon legende="Êtes-vous inscrit·e à Université Côte d'Azur ?" valeur={form.inscrit_uca} onChange={(v) => maj("inscrit_uca", v)} />
              <Champ
                id={`${id}-heures`}
                libelle="Heures d'enseignement en IA"
                type="number"
                min={0}
                max={5000}
                required
                className="max-w-32"
                aide={`Le règlement exige au moins ${reglement?.heures_ia_minimum ?? 24} heures.`}
                value={form.heures_ia}
                onChange={(e) => maj("heures_ia", e.target.value)}
              />
              <ChoixOuiNon legende="Suivez-vous cette formation en alternance ?" valeur={form.alternance} onChange={(v) => maj("alternance", v)} />
              <ChoixOuiNon
                legende="Bénéficiez-vous d'une autre bourse d'études en 2026-2027 ?"
                aide="La bourse CROUS sur critères sociaux est cumulable : déclarez-la quand même."
                valeur={form.autre_bourse}
                onChange={(v) => maj("autre_bourse", v)}
              />
              {form.autre_bourse && (
                <Champ id={`${id}-bourse`} libelle="Intitulé de la bourse" required maxLength={255} value={form.autre_bourse_libelle} onChange={(e) => maj("autre_bourse_libelle", e.target.value)} />
              )}
              <Champ
                id={`${id}-envoi`}
                libelle="Date d'envoi du dossier par e-mail (facultatif)"
                type="datetime-local"
                aide="À défaut, la date de dépôt sur cette application est retenue."
                value={form.date_envoi}
                onChange={(e) => maj("date_envoi", e.target.value)}
                className="max-w-64"
              />
              <div className="flex justify-end">
                <Button type="submit">Continuer</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {etape === 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Votre dossier PDF</CardTitle>
            <CardDescription>
              Un seul fichier regroupant toutes les pièces, {TAILLE_MAX_MO} Mo maximum.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={suivant} className="space-y-5">
              <div className="rounded-lg bg-muted px-4 py-3 text-sm">
                Nom attendu par le règlement :{" "}
                <code className="font-semibold break-all">{attendu}</code>
              </div>
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setSurvol(true);
                }}
                onDragLeave={() => setSurvol(false)}
                onDrop={deposerFichier}
                className={cn(
                  "flex flex-col items-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
                  survol ? "border-primary bg-accent" : "border-border",
                )}
              >
                <UploadCloud aria-hidden className="size-8 text-muted-foreground" />
                <p className="text-sm">
                  Glissez-déposez votre PDF ici, ou{" "}
                  <button
                    type="button"
                    className="font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                    onClick={() => entreeFichier.current?.click()}
                  >
                    parcourez vos fichiers
                  </button>
                </p>
                <input
                  ref={entreeFichier}
                  type="file"
                  accept="application/pdf,.pdf"
                  className="sr-only"
                  aria-label="Choisir le dossier PDF"
                  onChange={(e) => choisir(e.target.files?.[0])}
                />
              </div>
              <div aria-live="polite" className="space-y-3 empty:hidden">
                {erreurFichier && <Alerte variante="danger" titre={erreurFichier} />}
                {fichier && (
                  <div className="flex items-center gap-3 rounded-lg border p-3">
                    <FileText aria-hidden className="size-5 text-primary" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{fichier.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {(fichier.size / 1024 / 1024).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Mo
                      </p>
                    </div>
                    <Button type="button" variant="ghost" size="icon" aria-label="Retirer le fichier" onClick={() => setFichier(null)}>
                      <X aria-hidden />
                    </Button>
                  </div>
                )}
                {fichier && !nomConforme && (
                  <Alerte variante="attention" titre="Le nom du fichier ne suit pas le format attendu">
                    Ce n'est qu'un avertissement, mais renommez le fichier « {attendu} » avant
                    de l'envoyer à EFELIA.
                  </Alerte>
                )}
              </div>
              <div className="flex justify-between">
                <Button type="button" variant="ghost" onClick={() => setEtape(0)}>
                  Retour
                </Button>
                <Button type="submit" disabled={!fichier}>
                  Continuer
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {etape === 2 && fichier && (
        <Card>
          <CardHeader>
            <CardTitle>Confirmation</CardTitle>
            <CardDescription>Vérifiez les informations avant l'envoi.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={envoyer} className="space-y-5">
              <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
                <dt className="text-muted-foreground">Candidat·e</dt>
                <dd>{form.prenom} {form.nom}</dd>
                <dt className="text-muted-foreground">Formation</dt>
                <dd>{form.formation} — {form.heures_ia} h d'IA</dd>
                <dt className="text-muted-foreground">Fichier</dt>
                <dd className="break-all">{fichier.name}</dd>
              </dl>
              <div className="flex items-start gap-3 rounded-lg border p-4">
                <Checkbox
                  id={`${id}-consentement`}
                  checked={consentement}
                  onChange={(e) => setConsentement(e.target.checked)}
                  required
                  className="mt-0.5"
                />
                <Label htmlFor={`${id}-consentement`} className="font-normal leading-relaxed">
                  J'accepte que mon dossier soit analysé automatiquement, y compris par un modèle
                  d'IA, dans le seul but d'en vérifier la recevabilité. Mes justificatifs sociaux
                  ou médicaux ne sont jamais lus.{" "}
                  <Link to="/confidentialite" className="text-primary underline underline-offset-4">
                    Politique de confidentialité
                  </Link>
                </Label>
              </div>
              <div aria-live="polite" className="empty:hidden">
                {deposer.isError && (
                  <Alerte variante="danger" titre="Le dépôt a échoué">
                    {deposer.error instanceof ErreurApi ? deposer.error.message : "Réessayez dans un instant."}
                  </Alerte>
                )}
              </div>
              <div className="flex justify-between">
                <Button type="button" variant="ghost" onClick={() => setEtape(1)}>
                  Retour
                </Button>
                <Button type="submit" disabled={!consentement || deposer.isPending}>
                  {deposer.isPending && <Loader2 aria-hidden className="animate-spin" />}
                  Envoyer le dossier
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
