import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Award,
  BookOpen,
  CalendarClock,
  GraduationCap,
  HelpCircle,
  LayoutDashboard,
  Menu,
  Moon,
  PanelLeft,
  Settings,
  Sun,
} from "lucide-react";
import { useTheme } from "next-themes";
import * as React from "react";
import { NavLink, useLocation } from "react-router-dom";

import { Button, focusRing } from "@/components/ui/button";
import { SheetContent } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { ModeSwitch, modeFromPath } from "./ModeSwitch";

const NAV = {
  study: [{ to: "/estudo", label: "Painel", icon: LayoutDashboard }],
  manage: [
    { to: "/gerenciar/disciplinas", label: "Disciplinas e temas", icon: BookOpen },
    { to: "/gerenciar/provas", label: "Provas e prazos", icon: CalendarClock },
    { to: "/gerenciar/curso", label: "Semestres e curso", icon: GraduationCap },
    { to: "/gerenciar/acc", label: "Atividades complementares", icon: Award },
    { to: "/gerenciar/configuracoes", label: "Configurações", icon: Settings },
    { to: "/gerenciar/como-usar", label: "Como usar", icon: HelpCircle },
  ],
};

function SidebarNav({ collapsed, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const mode = modeFromPath(useLocation().pathname);
  return (
    <nav role="navigation" aria-label="Seções" className="flex flex-col gap-1 p-2">
      {NAV[mode].map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          onClick={onNavigate}
          title={collapsed ? label : undefined}
          className={({ isActive }) =>
            cn(
              "flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150 sm:min-h-0",
              isActive ? "bg-accent text-accent-foreground" : "text-foreground hover:bg-muted",
              focusRing,
            )
          }
        >
          <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
          <span className={cn(collapsed && "sr-only")}>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={dark ? "Usar tema claro" : "Usar tema escuro"}
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
    </Button>
  );
}

interface AppShellProps {
  children: React.ReactNode;
  /** Painel lateral direito (agente). A partir de lg é a terceira coluna. */
  rightPanel?: React.ReactNode;
  /** Botão da topbar que abre o painel direito abaixo de lg */
  rightPanelTrigger?: React.ReactNode;
}

export function AppShell({ children, rightPanel, rightPanelTrigger }: AppShellProps) {
  const [collapsed, setCollapsed] = React.useState(false);
  const [mobileOpen, setMobileOpen] = React.useState(false);

  return (
    <div className="flex h-[100dvh] flex-col">
      <a
        href="#conteudo"
        className="sr-only z-50 rounded-md bg-card px-4 py-2 focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Pular para o conteúdo
      </a>

      <header role="banner" className="sticky top-0 z-40 flex h-16 items-center gap-2 border-b border-border bg-card px-4">
        <DialogPrimitive.Root open={mobileOpen} onOpenChange={setMobileOpen}>
          <DialogPrimitive.Trigger asChild>
            <Button variant="ghost" size="icon" aria-label="Abrir menu" className="md:hidden">
              <Menu aria-hidden="true" />
            </Button>
          </DialogPrimitive.Trigger>
          <SheetContent side="left" title="Menu">
            <div className="flex h-16 items-center border-b border-border px-4 text-base font-semibold">Painel de Estudos</div>
            <div className="p-2 sm:hidden">
              <ModeSwitch stacked onNavigate={() => setMobileOpen(false)} />
            </div>
            <SidebarNav onNavigate={() => setMobileOpen(false)} />
          </SheetContent>
        </DialogPrimitive.Root>

        <Button
          variant="ghost"
          size="icon"
          aria-label={collapsed ? "Expandir menu lateral" : "Recolher menu lateral"}
          aria-expanded={!collapsed}
          className="hidden md:inline-flex"
          onClick={() => setCollapsed((c) => !c)}
        >
          <PanelLeft aria-hidden="true" />
        </Button>

        <span className="mr-2 truncate text-base font-semibold">Painel de Estudos</span>
        <div className="hidden sm:block">
          <ModeSwitch />
        </div>
        <div className="ml-auto flex items-center gap-2">
          {rightPanelTrigger}
          <ThemeToggle />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside
          aria-label="Menu lateral"
          className={cn(
            "relative hidden shrink-0 overflow-y-auto border-r border-border bg-card transition-[width] duration-300 md:block",
            collapsed ? "w-12" : "w-64",
          )}
        >
          <SidebarNav collapsed={collapsed} />
        </aside>

        <div className="relative flex min-w-0 flex-1 flex-col overflow-y-auto">
          <main
            role="main"
            id="conteudo"
            tabIndex={-1}
            className="mx-auto w-full max-w-[1280px] flex-1 px-6 py-6 focus:outline-none"
          >
            {children}
          </main>
          <footer role="contentinfo" className="mt-auto flex h-12 items-center border-t border-border px-6">
            <p className="text-xs text-muted-foreground">Roda só neste PC · dados em ./data</p>
          </footer>
        </div>

        {rightPanel}
      </div>
    </div>
  );
}
