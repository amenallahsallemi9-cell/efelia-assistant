import { ChevronLeft, ChevronRight, ExternalLink, Highlighter, ImageOff, Lock } from "lucide-react";
import { useEffect, useId, useState } from "react";

import type { PageDossier } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/champs";
import { Skeleton } from "@/components/ui/skeleton";
import { LIBELLES_PIECE } from "@/lib/format";

import type { Selection } from "./selection";

export function urlImage(dossierId: string, selection: Selection): string {
  const base = `/api/dossiers/${dossierId}/pages/${selection.page}/image`;
  return selection.extrait ? `${base}?surligner=${encodeURIComponent(selection.extrait.slice(0, 300))}` : base;
}

export function Visionneuse({
  dossierId,
  pages,
  selection,
  onSelectionner,
}: {
  dossierId: string;
  pages: PageDossier[];
  selection: Selection;
  onSelectionner: (s: Selection) => void;
}) {
  const idSelect = useId();
  const url = urlImage(dossierId, selection);
  const [etat, setEtat] = useState<"chargement" | "pret" | "erreur">("chargement");
  useEffect(() => setEtat("chargement"), [url]);

  const page = pages.find((p) => p.numero === selection.page);
  const total = pages.length;
  const aller = (numero: number) => onSelectionner({ page: numero, extrait: null });

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
        <Button variant="ghost" size="icon" aria-label="Page précédente" disabled={selection.page <= 1} onClick={() => aller(selection.page - 1)}>
          <ChevronLeft aria-hidden />
        </Button>
        <label htmlFor={idSelect} className="sr-only">Page affichée</label>
        <Select id={idSelect} value={selection.page} onChange={(e) => aller(Number(e.target.value))} className="h-8 w-auto">
          {pages.map((p) => (
            <option key={p.numero} value={p.numero}>
              Page {p.numero} — {p.type_piece ? LIBELLES_PIECE[p.type_piece] : "non classée"}
            </option>
          ))}
        </Select>
        <span className="text-sm text-muted-foreground">sur {total}</span>
        <Button variant="ghost" size="icon" aria-label="Page suivante" disabled={selection.page >= total} onClick={() => aller(selection.page + 1)}>
          <ChevronRight aria-hidden />
        </Button>
        <a href={url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 rounded text-xs text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          Agrandir <ExternalLink aria-hidden className="size-3.5" />
          <span className="sr-only">(nouvel onglet)</span>
        </a>
      </div>
      <div aria-live="polite" className="flex min-h-8 flex-wrap items-center gap-2 px-3 py-2 text-xs empty:hidden">
        {selection.extrait && (
          <span className="inline-flex min-w-0 items-center gap-1.5 text-muted-foreground">
            <Highlighter aria-hidden className="size-3.5 shrink-0 text-primary" />
            <span className="truncate">Extrait surligné : « {selection.extrait} »</span>
          </span>
        )}
        {page?.sensible && (
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">
            <Lock aria-hidden className="size-3.5" /> Justificatif sensible : aperçu masqué, contenu jamais lu.
          </span>
        )}
        {page?.methode === "ocr" && <span className="text-muted-foreground">Page scannée lue par OCR (pas de surlignage).</span>}
      </div>
      <div className="relative bg-muted/50 p-3">
        {etat === "chargement" && <Skeleton className="absolute inset-3 rounded-md" />}
        {etat === "erreur" ? (
          <div className="flex aspect-[1/1.414] flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
            <ImageOff aria-hidden className="size-6" /> Aperçu indisponible.
          </div>
        ) : (
          <img
            key={url}
            src={url}
            alt={`Page ${selection.page} du dossier${page?.type_piece ? ` : ${LIBELLES_PIECE[page.type_piece]}` : ""}`}
            onLoad={() => setEtat("pret")}
            onError={() => setEtat("erreur")}
            className="mx-auto aspect-[1/1.414] w-full max-w-xl rounded-md bg-white shadow-sm"
          />
        )}
      </div>
    </Card>
  );
}
