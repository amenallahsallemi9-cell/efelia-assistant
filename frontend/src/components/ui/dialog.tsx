import * as Fenetre from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

export const Dialog = Fenetre.Root;
export const DialogTrigger = Fenetre.Trigger;
export const DialogClose = Fenetre.Close;

export function DialogContent({
  className,
  titre,
  description,
  children,
  ...props
}: ComponentProps<typeof Fenetre.Content> & { titre: ReactNode; description?: ReactNode }) {
  return (
    <Fenetre.Portal>
      <Fenetre.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-[1px]" />
      <Fenetre.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 grid w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 gap-4 rounded-xl border bg-card p-6 shadow-lg focus-visible:outline-none",
          className,
        )}
        {...props}
      >
        <div className="space-y-1.5">
          <Fenetre.Title className="text-lg font-semibold">{titre}</Fenetre.Title>
          {description && (
            <Fenetre.Description className="text-sm text-muted-foreground">
              {description}
            </Fenetre.Description>
          )}
        </div>
        {children}
        <Fenetre.Close
          aria-label="Fermer"
          className="absolute right-4 top-4 rounded-sm opacity-70 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X aria-hidden className="size-4" />
        </Fenetre.Close>
      </Fenetre.Content>
    </Fenetre.Portal>
  );
}
