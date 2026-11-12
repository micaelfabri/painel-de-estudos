import * as React from "react";

import { cn } from "@/lib/utils";

// Badge de categoria: rounded-md. (Badge de status, rounded-full com ponto, não é usado no painel.)
export function CategoryBadge({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium [&_svg]:size-3", className)}
      {...props}
    />
  );
}
