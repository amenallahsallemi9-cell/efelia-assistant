import { Construction } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/** Page provisoire pendant la construction des phases suivantes. */
export function PageAVenir({ titre }: { titre: string }) {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{titre}</h1>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Construction aria-hidden className="size-4 text-muted-foreground" />
            En construction
          </CardTitle>
          <CardDescription>Cette page sera disponible dans une prochaine phase.</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
    </div>
  );
}
