import * as Accordeon from "@radix-ui/react-accordion";
import { ChevronDown } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export const Accordion = Accordeon.Root;

export function AccordionItem({ className, ...props }: ComponentProps<typeof Accordeon.Item>) {
  return <Accordeon.Item className={cn("border-b last:border-b-0", className)} {...props} />;
}

export function AccordionTrigger({
  className,
  children,
  ...props
}: ComponentProps<typeof Accordeon.Trigger>) {
  return (
    <Accordeon.Header className="flex">
      <Accordeon.Trigger
        className={cn(
          "flex flex-1 items-center justify-between gap-4 rounded-md py-4 text-left text-sm font-medium transition-all hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&[data-state=open]>svg]:rotate-180",
          className,
        )}
        {...props}
      >
        {children}
        <ChevronDown aria-hidden className="size-4 shrink-0 text-muted-foreground transition-transform" />
      </Accordeon.Trigger>
    </Accordeon.Header>
  );
}

export function AccordionContent({
  className,
  children,
  ...props
}: ComponentProps<typeof Accordeon.Content>) {
  return (
    <Accordeon.Content className="overflow-hidden text-sm" {...props}>
      <div className={cn("pb-4", className)}>{children}</div>
    </Accordeon.Content>
  );
}
