import * as React from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AgentProvider } from "@/components/agent/AgentContext";
import { AgentAside, AgentSheetTrigger } from "@/components/agent/AgentPanel";

import { AppShell } from "@/components/layout/AppShell";
import { AppToaster } from "@/components/layout/AppToaster";
import { StudyPage } from "@/pages/StudyPage";

// Cada página (menos o Painel, que abre primeiro) vira um arquivo próprio, baixado só ao abrir
const AgendaPage = React.lazy(() => import("@/pages/AgendaPage").then((m) => ({ default: m.AgendaPage })));
const HistoryPage = React.lazy(() => import("@/pages/HistoryPage").then((m) => ({ default: m.HistoryPage })));
const CardsPage = React.lazy(() => import("@/pages/CardsPage").then((m) => ({ default: m.CardsPage })));
const PerformancePage = React.lazy(() =>
  import("@/pages/PerformancePage").then((m) => ({ default: m.PerformancePage })),
);
const AccPage = React.lazy(() => import("@/pages/manage/AccPage").then((m) => ({ default: m.AccPage })));
const ExamsPage = React.lazy(() => import("@/pages/manage/ExamsPage").then((m) => ({ default: m.ExamsPage })));
const HelpPage = React.lazy(() => import("@/pages/manage/HelpPage").then((m) => ({ default: m.HelpPage })));
const SemestersPage = React.lazy(() =>
  import("@/pages/manage/SemestersPage").then((m) => ({ default: m.SemestersPage })),
);
const SettingsPage = React.lazy(() => import("@/pages/manage/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const SubjectsPage = React.lazy(() => import("@/pages/manage/SubjectsPage").then((m) => ({ default: m.SubjectsPage })));

export function App() {
  // O agente aparece no modo Estudo; o estado fica no provider e sobrevive à troca de modo
  const study = !useLocation().pathname.startsWith("/gerenciar");
  return (
    <AgentProvider>
      <AppToaster />
      <AppShell
        rightPanel={study ? <AgentAside /> : undefined}
        rightPanelTrigger={study ? <AgentSheetTrigger /> : undefined}
      >
        <React.Suspense fallback={<p className="text-sm text-muted-foreground">Carregando…</p>}>
          <Routes>
            <Route path="/" element={<Navigate to="/estudo" replace />} />
            <Route path="/estudo" element={<StudyPage />} />
            <Route path="/estudo/provas" element={<AgendaPage />} />
            <Route path="/estudo/historico" element={<HistoryPage />} />
            <Route path="/estudo/cards" element={<CardsPage />} />
            <Route path="/estudo/desempenho" element={<PerformancePage />} />
            <Route path="/gerenciar" element={<Navigate to="/gerenciar/disciplinas" replace />} />
            <Route path="/gerenciar/disciplinas" element={<SubjectsPage />} />
            <Route path="/gerenciar/provas" element={<ExamsPage />} />
            <Route path="/gerenciar/curso" element={<SemestersPage />} />
            <Route path="/gerenciar/acc" element={<AccPage />} />
            <Route path="/gerenciar/configuracoes" element={<SettingsPage />} />
            <Route path="/gerenciar/como-usar" element={<HelpPage />} />
            <Route path="*" element={<Navigate to="/estudo" replace />} />
          </Routes>
        </React.Suspense>
      </AppShell>
    </AgentProvider>
  );
}
