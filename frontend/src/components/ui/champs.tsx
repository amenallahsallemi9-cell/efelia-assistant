import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

const BASE =
  "w-full rounded-md border border-input bg-card px-3 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-destructive";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return <input className={cn(BASE, "h-9 py-1", className)} {...props} />;
}

export function Select({ className, ...props }: ComponentProps<"select">) {
  return <select className={cn(BASE, "h-9 py-1 pr-8", className)} {...props} />;
}

export function Label({ className, ...props }: ComponentProps<"label">) {
  return <label className={cn("block text-sm font-medium leading-none", className)} {...props} />;
}

export function Checkbox({ className, ...props }: Omit<ComponentProps<"input">, "type">) {
  return (
    <input
      type="checkbox"
      className={cn(
        "size-4 shrink-0 rounded border-input accent-[var(--primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
      {...props}
    />
  );
}

/** Message d'aide ou d'erreur sous un champ. */
export function AideChamp({
  erreur,
  className,
  ...props
}: ComponentProps<"p"> & { erreur?: boolean }) {
  return (
    <p
      className={cn("text-xs", erreur ? "text-destructive" : "text-muted-foreground", className)}
      {...props}
    />
  );
}
