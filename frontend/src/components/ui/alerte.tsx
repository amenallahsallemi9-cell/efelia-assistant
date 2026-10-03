import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

const STYLES = {
  info: { icone: Info, classes: "border-border bg-card text-foreground [&_svg]:text-primary" },
  succes: { icone: CheckCircle2, classes: "border-transparent bg-succes-fond text-succes" },
  attention: { icone: AlertTriangle, classes: "border-transparent bg-attention-fond text-attention" },
  danger: { icone: XCircle, classes: "border-transparent bg-danger-fond text-danger" },
};

type AlerteProps = Omit<ComponentProps<"div">, "title"> & {
  variante?: keyof typeof STYLES;
  titre?: ReactNode;
};

export function Alerte({ variante = "info", titre, children, className, ...props }: AlerteProps) {
  const { icone: Icone, classes } = STYLES[variante];
  return (
    <div
      role={variante === "danger" ? "alert" : "status"}
      className={cn("flex gap-3 rounded-lg border p-4 text-sm", classes, className)}
      {...props}
    >
      <Icone aria-hidden className="mt-0.5 size-4 shrink-0" />
      <div className="space-y-1">
        {titre && <p className="font-medium">{titre}</p>}
        {children && <div className="text-foreground/80">{children}</div>}
      </div>
    </div>
  );
}
