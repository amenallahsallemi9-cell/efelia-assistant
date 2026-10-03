import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

const variantesBadge = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap [&_svg]:size-3.5",
  {
    variants: {
      variant: {
        neutre: "border-border bg-secondary text-secondary-foreground",
        succes: "border-transparent bg-succes-fond text-succes",
        attention: "border-transparent bg-attention-fond text-attention",
        danger: "border-transparent bg-danger-fond text-danger",
        info: "border-transparent bg-accent text-accent-foreground",
      },
    },
    defaultVariants: { variant: "neutre" },
  },
);

export type BadgeProps = ComponentProps<"span"> & VariantProps<typeof variantesBadge>;

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(variantesBadge({ variant }), className)} {...props} />;
}
