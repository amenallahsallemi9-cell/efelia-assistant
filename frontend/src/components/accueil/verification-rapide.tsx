import { ArrowRight, Loader2 } from "lucide-react";
import { type FormEvent, useId, useState } from "react";
import { Link } from "react-router-dom";

import { ErreurApi } from "@/api/client";
import { useReglement, useVerifierEligibilite } from "@/api/reglement";
import type { DemandeEligibilite } from "@/api/types";
import { IconeResultat } from "@/components/statut/statuts";
import { Alerte } from "@/components/ui/alerte";
import { Button, variantesBouton } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AideChamp, Input, Label } from "@/components/ui/champs";
import { ChoixOuiNon as Choix } from "@/components/ui/choix";

export function VerificationRapide() {
  const { data: reglement } = useReglement();
  const verifier = useVerifierEligibilite();
  const idHeures = useId();
  const idBourse = useId();
  const [inscrit, setInscrit] = useState<boolean | null>(null);
  const [heures, setHeures] = useState("");
  const [alternance, setAlternance] = useState<boolean | null>(null);
  const [autreBourse, setAutreBourse] = useState<boolean | null>(null);
  const [libelle, setLibelle] = useState("");

  const soumettre = (evenement: FormEvent) => {
    evenement.preventDefault();
    const demande: DemandeEligibilite = {
      inscrit_uca: inscrit === true,
      heures_ia: Number(heures),
      alternance: alternance === true,
      autre_bourse: autreBourse === true,
      autre_bourse_libelle: autreBourse ? libelle || null : null,
    };
    verifier.mutate(demande);
  };

  const resultat = verifier.data;
  const eligibilite = resultat?.controles.filter((c) => c.categorie === "eligibilite") ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Vérification rapide</CardTitle>
        <CardDescription>
          Quatre questions pour savoir si vous pouvez candidater. Aucune donnée n'est conservée.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={soumettre} className="space-y-5">
          <Choix legende="Êtes-vous inscrit·e à Université Côte d'Azur ?" valeur={inscrit} onChange={setInscrit} />
          <div className="space-y-2">
            <Label htmlFor={idHeures}>Heures d'enseignement en IA dans votre formation</Label>
            <Input
              id={idHeures}
              type="number"
              inputMode="numeric"
              min={0}
              max={5000}
              required
              value={heures}
              onChange={(e) => setHeures(e.target.value)}
              className="max-w-32"
              aria-describedby={`${idHeures}-aide`}
            />
            <AideChamp id={`${idHeures}-aide`}>
              Minimum requis : {reglement?.heures_ia_minimum ?? 24} heures.
            </AideChamp>
          </div>
          <Choix legende="Suivez-vous votre formation en alternance ?" valeur={alternance} onChange={setAlternance} />
          <Choix
            legende="Bénéficiez-vous d'une autre bourse d'études cette année ?"
            valeur={autreBourse}
            onChange={setAutreBourse}
          />
          {autreBourse && (
            <div className="space-y-2">
              <Label htmlFor={idBourse}>Laquelle ?</Label>
              <Input
                id={idBourse}
                value={libelle}
                maxLength={255}
                placeholder="Ex. : bourse CROUS sur critères sociaux, échelon 4"
                onChange={(e) => setLibelle(e.target.value)}
              />
              <AideChamp>La bourse CROUS sur critères sociaux est cumulable.</AideChamp>
            </div>
          )}
          <Button type="submit" disabled={verifier.isPending}>
            {verifier.isPending && <Loader2 aria-hidden className="animate-spin" />}
            Vérifier
          </Button>
        </form>

        <div aria-live="polite" className="mt-6 empty:hidden">
          {verifier.isError && (
            <Alerte variante="danger" titre="Vérification impossible">
              {verifier.error instanceof ErreurApi ? verifier.error.message : "Réessayez dans un instant."}
            </Alerte>
          )}
          {resultat && (
            <div className="space-y-4">
              <Alerte
                variante={resultat.eligible && resultat.dans_les_delais ? "succes" : resultat.eligible ? "attention" : "danger"}
                titre={resultat.message}
              />
              <ul className="space-y-2">
                {eligibilite.map((c) => (
                  <li key={c.code} className="flex gap-2 text-sm">
                    <IconeResultat resultat={c.resultat} className="mt-0.5" />
                    <span>
                      <span className="font-medium">{c.libelle}.</span>{" "}
                      <span className="text-muted-foreground">{c.message}</span>
                    </span>
                  </li>
                ))}
              </ul>
              {resultat.eligible && resultat.dans_les_delais && (
                <Link to="/deposer" className={variantesBouton({ variant: "outline" })}>
                  Préparer mon dossier <ArrowRight aria-hidden />
                </Link>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
