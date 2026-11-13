import * as React from "react";

import { cn } from "@/lib/utils";

// Badge de categoria: rounded-md.
export function CategoryBadge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium [&_svg]:size-3",
        className,
      )}
      {...props}
    />
  );
}

/**
 * Badge de status: rounded-full com ponto (estado, não categoria). O texto sempre aparece; a cor
 * nunca carrega o significado sozinha. Usado no ciclo dos erros (resposta 03 do DS).
 */
export function StatusBadge({
  className,
  dotClassName,
  children,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { dotClassName?: string }) {
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium", className)}
      {...props}
    >
      <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full bg-current", dotClassName)} aria-hidden="true" />
      {children}
    </span>
  );
}
