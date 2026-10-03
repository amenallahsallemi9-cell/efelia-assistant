import * as Onglets from "@radix-ui/react-tabs";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export const Tabs = Onglets.Root;

export function TabsList({ className, ...props }: ComponentProps<typeof Onglets.List>) {
  return (
    <Onglets.List
      className={cn(
        "inline-flex h-9 max-w-full items-center gap-1 overflow-x-auto rounded-lg bg-muted p-1 text-muted-foreground",
        className,
      )}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof Onglets.Trigger>) {
  return (
    <Onglets.Trigger
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[state=active]:bg-card data-[state=active]:text-foreground data-[state=active]:shadow-sm [&_svg]:size-4 [&_svg]:max-sm:hidden",
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({ className, ...props }: ComponentProps<typeof Onglets.Content>) {
  return <Onglets.Content className={cn("mt-4 focus-visible:outline-none", className)} {...props} />;
}
