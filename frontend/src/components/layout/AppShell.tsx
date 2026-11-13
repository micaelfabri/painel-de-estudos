import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Award,
  BarChart3,
  BookOpen,
  CalendarClock,
  GraduationCap,
  HelpCircle,
  History,
  Layers,
  LayoutDashboard,
  Menu,
  Moon,
  PanelLeft,
  Settings,
  Sun,
  type LucideIcon,
} from "lucide-react";
import { useTheme } from "next-themes";
import * as React from "react";
import { NavLink, useLocation } from "react-router-dom";

import { Button, focusRing } from "@/components/ui/button";
import { SheetContent } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { AppFooter } from "./AppFooter";
import { ModeSwitch, modeFromPath } from "./ModeSwitch";

type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
  /** Ativo também em subpáginas (ex.: Meus cursos na página de um curso) */
  match?: (path: string) => boolean;
};

// v1.8 (D38): no Estudo, dois grupos — a faculdade e os cursos fora dela
const STUDY_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Faculdade",
    items: [
      { to: "/estudo", label: "Painel", icon: LayoutDashboard, end: true },
      { to: "/estudo/provas", label: "Provas e prazos", icon: CalendarClock },
      { to: "/estudo/historico", label: "Histórico", icon: History },
      { to: "/estudo/cards", label: "Cards", icon: Layers },
      { to: "/estudo/desempenho", label: "Desempenho", icon: BarChart3 },
    ],
  },
  {
    label: "Cursos e certificados",
    items: [
      {
        to: "/cursos",
        label: "Meus cursos",
        icon: GraduationCap,
        match: (p) => p === "/cursos" || /^\/cursos\/\d+/.test(p),
      },
      { to: "/cursos/historico", label: "Histórico", icon: History },
      { to: "/cursos/cards", label: "Cards", icon: Layers },
      { to: "/cursos/desempenho", label: "Desempenho", icon: BarChart3 },
    ],
  },
];

const NAV = {
  manage: [
    {
      to: "/gerenciar/disciplinas",
      label: "Disciplinas e temas",
      icon: BookOpen,
    },
    { to: "/gerenciar/provas", label: "Provas e prazos", icon: CalendarClock },
    { to: "/gerenciar/curso", label: "Semestres e curso", icon: GraduationCap },
    { to: "/gerenciar/acc", label: "Atividades complementares", icon: Award },
    { to: "/gerenciar/configuracoes", label: "Configurações", icon: Settings },
    { to: "/gerenciar/como-usar", label: "Como usar", icon: HelpCircle },
  ],
};

function NavItemLink({
  item,
  collapsed,
  onNavigate,
  pathname,
}: {
  item: NavItem;
  collapsed?: boolean;
  onNavigate?: () => void;
  pathname: string;
}) {
  const { to, label, icon: Icon, end, match } = item;
  return (
    <NavLink
      to={to}
      end={end ?? !!match}
      onClick={onNavigate}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        cn(
          "flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150 sm:min-h-0",
          isActive || match?.(pathname) ? "bg-accent text-accent-foreground" : "text-foreground hover:bg-muted",
          focusRing,
        )
      }
    >
      <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
      <span className={cn(collapsed && "sr-only")}>{label}</span>
    </NavLink>
  );
}

function SidebarNav({ collapsed, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }) {
  const pathname = useLocation().pathname;
  const mode = modeFromPath(pathname);
  if (mode === "study")
    return (
      <nav role="navigation" aria-label="Seções" className="flex flex-col gap-1 p-2">
        {STUDY_GROUPS.map((group, i) => (
          <div key={group.label} role="group" aria-labelledby={`nav-group-${i}`} className="flex flex-col gap-1">
            {i > 0 && <div className="my-2 h-px bg-border" aria-hidden="true" />}
            <p
              id={`nav-group-${i}`}
              className={cn(
                "px-3 pb-1 pt-2 text-xs font-medium uppercase tracking-wider text-muted-foreground",
                collapsed && "sr-only",
              )}
            >
              {group.label}
            </p>
            {group.items.map((item) => (
              <NavItemLink
                key={item.to}
                item={item}
                collapsed={collapsed}
                onNavigate={onNavigate}
                pathname={pathname}
              />
            ))}
          </div>
        ))}
      </nav>
    );
  return (
    <nav role="navigation" aria-label="Seções" className="flex flex-col gap-1 p-2">
      {NAV.manage.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={false}
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

      <header
        role="banner"
        className="sticky top-0 z-40 flex h-16 items-center gap-2 border-b border-border bg-card px-4"
      >
        <DialogPrimitive.Root open={mobileOpen} onOpenChange={setMobileOpen}>
          <DialogPrimitive.Trigger asChild>
            <Button variant="ghost" size="icon" aria-label="Abrir menu" className="md:hidden">
              <Menu aria-hidden="true" />
            </Button>
          </DialogPrimitive.Trigger>
          <SheetContent side="left" title="Menu">
            <div className="flex h-16 items-center border-b border-border px-4 text-base font-semibold">
              Painel de Estudos
            </div>
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
          <AppFooter />
        </div>

        {rightPanel}
      </div>
    </div>
  );
}
