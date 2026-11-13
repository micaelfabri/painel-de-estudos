import * as React from "react";
import { toast } from "sonner";

import { useAgent } from "@/components/agent/AgentContext";
import { CardOfDay } from "@/components/cards/CardOfDay";
import { startDue } from "@/components/cards/CardSessionView";
import { TopicsDialog } from "@/components/manage/TopicsDialog";
import { PendingCard, WeekSummaryCard } from "@/components/panel/StudyExtras";
import { TopicScoresCard } from "@/components/panel/TopicScoresCard";
import { Card, CardContent } from "@/components/ui/card";
import { FourteenDayStrip } from "@/components/panel/FourteenDayStrip";
import { SubjectCard } from "@/components/panel/SubjectCard";
import { NextActionCard, NextExamCard, WeekHoursCard } from "@/components/panel/SummaryCards";
import { TimerCard } from "@/components/panel/TimerCard";
import { TimerSessionsCard } from "@/components/panel/TimerSessionsCard";
import {
  api,
  type AgendaItem,
  type GoogleEvent,
  type Overview,
  type SettingsResponse,
  type Subject,
  type TopicScore,
  type WeekSummary,
} from "@/lib/api";
import { formatFullDate, parseLocalDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";

/** Modo Estudo: ordem canônica Header → Stats → Dados */
export function StudyPage() {
  const { data, error, loading, reload } = useApi<Overview>("/overview");
  const topics = useApi<TopicScore[]>("/learning/topics");
  const settings = useApi<SettingsResponse>("/settings");
  const week = useApi<WeekSummary>("/study/week");
  const agenda = useApi<AgendaItem[]>("/study/agenda");
  const [topicsOf, setTopicsOf] = React.useState<Subject | null>(null);
  const [timerVersion, setTimerVersion] = React.useState(0);
  // F5: eventos da agenda principal (só leitura); sem Google conectado vem lista vazia
  const calendar = useApi<{ connected: boolean; events: GoogleEvent[] }>(
    data ? `/google/events?start=${data.today}` : null,
  );
  const timeline = React.useMemo(() => {
    if (!data) return [];
    const events = calendar.data?.events ?? [];
    return data.timeline.map((day) => ({
      ...day,
      items: [
        ...day.items,
        ...events
          .filter((e) => e.date === day.date)
          .map((e) => ({
            category: "event" as const,
            title: e.title,
            time: e.time,
          })),
      ],
    }));
  }, [data, calendar.data]);
  const { learningVersion, openCards } = useAgent();
  const reloadTopics = topics.reload;
  const reloadWeek = week.reload;

  // Quando um conjunto de questões fecha no agente, nota e próxima ação mudam
  React.useEffect(() => {
    if (learningVersion > 0) {
      void reload();
      void reloadTopics();
      void reloadWeek();
    }
  }, [learningVersion, reload, reloadTopics, reloadWeek]);

  if (error) {
    return (
      <Card role="alert">
        <CardContent className="text-sm text-destructive-text">Não foi possível carregar o painel: {error}</CardContent>
      </Card>
    );
  }
  if (loading && !data) {
    return <p className="text-sm text-muted-foreground cursor-wait">Carregando…</p>;
  }
  if (!data) return null;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Painel de Estudos</h1>
        <p className="text-sm text-muted-foreground">
          {formatFullDate(parseLocalDate(data.today))}
          {data.semester && ` · Semestre ${data.semester.code} · ${data.semester.degree_name}`}
        </p>
      </header>

      <section aria-label="Resumo" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <NextExamCard exams={data.upcoming_exams} />
        <WeekHoursCard week={data.week} today={data.today} />
        <NextActionCard
          action={data.next_action}
          cardsDue={data.cards_due}
          onCards={() => void startDue(openCards).then((ok) => ok && toast.success("Aberto no painel do agente"))}
        />
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <CardOfDay onAnswered={() => void reload()} />
      </div>

      <section aria-label="Semana e pendências" className="grid gap-4 lg:grid-cols-2">
        <WeekSummaryCard week={week.data} />
        <PendingCard items={agenda.data ?? []} today={data.today} />
      </section>

      <section id="cronometro" aria-label="Cronômetro" className="grid gap-4">
        <TimerCard
          subjects={data.subjects}
          goalMinutes={data.timer.goal_minutes}
          alarmMinutes={data.timer.alarm_minutes}
          onSaved={() => {
            void reload();
            void reloadWeek();
            setTimerVersion((v) => v + 1);
          }}
        />
        <TimerSessionsCard limit={5} version={timerVersion} />
      </section>

      <section aria-labelledby="disciplinas" className="space-y-4">
        <div className="flex items-baseline justify-between gap-4">
          <h2 id="disciplinas" className="text-lg font-semibold">
            Disciplinas {data.semester?.code}
          </h2>
          <p className="text-xs text-muted-foreground">progresso digitado do portal</p>
        </div>
        {data.subjects.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma disciplina no semestre atual. Cadastre em Gerenciar.</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
            {data.subjects.map((s) => (
              <SubjectCard
                key={s.id}
                subject={s}
                onEditTopics={() => void api.get<Subject>(`/subjects/${s.id}`).then(setTopicsOf)}
              />
            ))}
          </div>
        )}
      </section>

      <TopicScoresCard topics={topics.data ?? []} threshold={Number(settings.data?.values.learned_threshold ?? 0.7)} />
      <FourteenDayStrip days={timeline} today={data.today} />
      <TopicsDialog
        subject={topicsOf}
        onOpenChange={(o) => !o && setTopicsOf(null)}
        onSaved={() => {
          setTopicsOf(null);
          void reload();
        }}
      />
    </div>
  );
}
