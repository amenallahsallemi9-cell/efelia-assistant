import { Loader2, RotateCcw, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ErreurApi } from "@/api/client";
import { useRelancer, useSupprimer } from "@/api/dossiers";
import { Alerte } from "@/components/ui/alerte";
import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogTrigger } from "@/components/ui/dialog";

export function ActionsDossier({ dossierId, peutRelancer }: { dossierId: string; peutRelancer: boolean }) {
  const navigate = useNavigate();
  const relancer = useRelancer(dossierId);
  const supprimer = useSupprimer();
  const [ouverte, setOuverte] = useState(false);

  return (
    <div className="flex flex-wrap gap-2">
      <Button
        variant="outline"
        size="sm"
        disabled={!peutRelancer || relancer.isPending}
        onClick={() => relancer.mutate(undefined, { onSuccess: () => navigate(`/dossiers/${dossierId}/suivi`) })}
      >
        {relancer.isPending ? <Loader2 aria-hidden className="animate-spin" /> : <RotateCcw aria-hidden />}
        Relancer l'instruction
      </Button>
      <Dialog open={ouverte} onOpenChange={setOuverte}>
        <DialogTrigger asChild>
          <Button variant="outline" size="sm" className="text-danger hover:text-danger">
            <Trash2 aria-hidden /> Supprimer
          </Button>
        </DialogTrigger>
        <DialogContent
          titre="Supprimer ce dossier ?"
          description="Le fichier, le texte extrait, les données lues, les embeddings, les décisions et la trace de l'agent seront définitivement effacés."
        >
          {supprimer.isError && (
            <Alerte variante="danger" titre="Suppression impossible">
              {supprimer.error instanceof ErreurApi ? supprimer.error.message : "Réessayez."}
            </Alerte>
          )}
          <div className="flex justify-end gap-2">
            <DialogClose asChild>
              <Button variant="ghost">Annuler</Button>
            </DialogClose>
            <Button
              variant="destructive"
              disabled={supprimer.isPending}
              onClick={() => supprimer.mutate(dossierId, { onSuccess: () => navigate("/dossiers", { replace: true }) })}
            >
              {supprimer.isPending && <Loader2 aria-hidden className="animate-spin" />}
              Supprimer définitivement
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      {relancer.isError && (
        <p role="alert" className="w-full text-sm text-danger">
          {relancer.error instanceof ErreurApi ? relancer.error.message : "La relance a échoué."}
        </p>
      )}
    </div>
  );
}
