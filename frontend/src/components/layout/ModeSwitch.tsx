import { Link, useLocation } from "react-router-dom";

import { focusRing } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Mode = "study" | "manage";

export function modeFromPath(pathname: string): Mode {
  return pathname.startsWith("/gerenciar") ? "manage" : "study";
}

const MODES: { mode: Mode; to: string; label: string }[] = [
  { mode: "study", to: "/estudo", label: "Estudo" },
  { mode: "manage", to: "/gerenciar/disciplinas", label: "Gerenciar" },
];

/** Seletor de modo (DS v2.13): navegação, não Tabs — dois links com visual de TabsList */
export function ModeSwitch({ stacked, onNavigate }: { stacked?: boolean; onNavigate?: () => void }) {
  const current = modeFromPath(useLocation().pathname);
  return (
    <nav aria-label="Modo" className={cn("inline-flex w-auto rounded-md bg-muted p-1", stacked && "flex w-full")}>
      {MODES.map(({ mode, to, label }) => {
        const active = mode === current;
        return (
          <Link
            key={mode}
            to={to}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex h-11 items-center justify-center rounded-sm px-3 text-sm font-medium transition-colors duration-150 sm:h-8",
              stacked && "flex-1",
              active ? "bg-card text-foreground" : "text-muted-foreground hover:text-foreground",
              focusRing,
            )}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
