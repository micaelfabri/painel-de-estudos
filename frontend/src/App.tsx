import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { AgentProvider } from "@/components/agent/AgentContext";
import { AgentAside, AgentSheetTrigger } from "@/components/agent/AgentPanel";

import { AppShell } from "@/components/layout/AppShell";
import { AppToaster } from "@/components/layout/AppToaster";
import { StudyPage } from "@/pages/StudyPage";
import { AccPage } from "@/pages/manage/AccPage";
import { ExamsPage } from "@/pages/manage/ExamsPage";
import { HelpPage } from "@/pages/manage/HelpPage";
import { SemestersPage } from "@/pages/manage/SemestersPage";
import { SettingsPage } from "@/pages/manage/SettingsPage";
import { SubjectsPage } from "@/pages/manage/SubjectsPage";

export function App() {
  // O agente aparece no modo Estudo; o estado fica no provider e sobrevive à troca de modo
  const study = !useLocation().pathname.startsWith("/gerenciar");
  return (
    <AgentProvider>
      <AppToaster />
      <AppShell rightPanel={study ? <AgentAside /> : undefined} rightPanelTrigger={study ? <AgentSheetTrigger /> : undefined}>
        <Routes>
          <Route path="/" element={<Navigate to="/estudo" replace />} />
          <Route path="/estudo" element={<StudyPage />} />
          <Route path="/gerenciar" element={<Navigate to="/gerenciar/disciplinas" replace />} />
          <Route path="/gerenciar/disciplinas" element={<SubjectsPage />} />
          <Route path="/gerenciar/provas" element={<ExamsPage />} />
          <Route path="/gerenciar/curso" element={<SemestersPage />} />
          <Route path="/gerenciar/acc" element={<AccPage />} />
          <Route path="/gerenciar/configuracoes" element={<SettingsPage />} />
          <Route path="/gerenciar/como-usar" element={<HelpPage />} />
          <Route path="*" element={<Navigate to="/estudo" replace />} />
        </Routes>
      </AppShell>
    </AgentProvider>
  );
}
