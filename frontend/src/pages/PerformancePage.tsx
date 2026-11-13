import * as React from "react";

import { toast } from "sonner";

import { HoursChart, ScoresChart } from "@/components/performance/Charts";
import { CategoryBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardEyebrow } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { InlineMeter } from "@/components/panel/InlineMeter";
import { TimerSessionsCard } from "@/components/panel/TimerSessionsCard";
import { useAgent } from "@/components/agent/AgentContext";
import type { DayDetail, Metrics } from "@/lib/api";
import { formatDuration, formatLongDate, formatTime, parseLocalDate, parseLocalDateTime } from "@/lib/format";
import { mistakeSummary } from "@/lib/mistakes";
import { useApi } from "@/lib/useApi";
import { useCoarsePointer } from "@/lib/usePointer";
import { cn } from "@/lib/utils";

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardContent className="space-y-1">
        <CardEyebrow>{label}</CardEyebrow>
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
        {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

/** v1.5: o que foi feito no dia clicado no gráfico de horas */
function DayCard({
  day,
  subjectId,
  onOpen,
  onClose,
}: {
  day: string;
  subjectId: string;
  onOpen: (id: number) => void;
  onClose: () => void;
}) {
  const detail = useApi<DayDetail>(`/study/day?day=${day}${subjectId !== "all" ? `&subject_id=${subjectId}` : ""}`);
  const d = detail.data;
  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardEyebrow>Dia selecionado</CardEyebrow>
            <h2 className="text-base font-semibold">{formatLongDate(parseLocalDate(day))}</h2>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Fechar
          </Button>
        </div>
        {!d ? (
          <p className="text-sm text-muted-foreground">Carregando…</p>
        ) : d.chunks.length === 0 && d.sets.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nada registrado neste dia.</p>
        ) : (
          <div className="grid gap-6 md:grid-cols-2">
            <section aria-label="Cronômetro" className="space-y-2">
              <p className="text-sm font-medium">Cronômetro · {formatDuration(d.seconds)}</p>
              {d.chunks.length === 0 ? (
                <p className="text-sm text-muted-foreground">Sem trechos.</p>
              ) : (
                <ul className="divide-y divide-border text-sm">
                  {d.chunks.map((c) => (
                    <li key={c.started_at} className="flex gap-3 py-2">
                      <span className="w-12 shrink-0 tabular-nums text-muted-foreground">
                        {formatTime(parseLocalDateTime(c.started_at))}
                      </span>
                      <span className="min-w-0 flex-1">{c.subject_name ?? "Sem disciplina"}</span>
                      <span className="tabular-nums">{formatDuration(c.seconds)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section aria-label="Testes" className="space-y-2">
              <p className="text-sm font-medium">Testes · {d.sets.length}</p>
              {d.sets.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhum teste concluído.</p>
              ) : (
                <ul className="divide-y divide-border text-sm">
                  {d.sets.map((t) => (
                    <li key={t.id} className="flex items-center gap-3 py-2">
                      <span className="min-w-0 flex-1">
                        {t.topic_title}
                        <span className="block text-xs text-muted-foreground">{t.label}</span>
                      </span>
                      <span className="font-semibold tabular-nums">{pct(t.score)}</span>
                      <Button variant="ghost" size="sm" onClick={() => onOpen(t.id)}>
                        Abrir
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** Estudo › Desempenho (SPEC D25): métricas além do painel, por período */
export function PerformancePage() {
  const [days, setDays] = React.useState("30");
  const [subject, setSubject] = React.useState("all");
  const [day, setDay] = React.useState<string | null>(null);
  const coarse = useCoarsePointer();
  const metrics = useApi<Metrics>(`/study/metrics?days=${days}${subject !== "all" ? `&subject_id=${subject}` : ""}`);
  const { learningVersion, openSet } = useAgent();
  const subjects = React.useRef<{ value: string; label: string }[]>([]);
  if (metrics.data && subject === "all")
    subjects.current = metrics.data.by_subject.map((s) => ({ value: String(s.subject_id), label: s.name }));
  const open = async (id: number) => {
    try {
      await openSet(id);
      toast.success("Aberto no painel do agente");
    } catch {
      toast.error("Não foi possível abrir o teste.");
    }
  };
  const reload = metrics.reload;
  React.useEffect(() => {
    if (learningVersion > 0) void reload();
  }, [learningVersion, reload]);
  const m = metrics.data;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Desempenho</h1>
          <p className="text-sm text-muted-foreground">Horas, notas, temas e foco no período escolhido.</p>
        </div>
      </header>
      {/* Filtros numa linha acima de tudo: período primeiro, depois a disciplina */}
      <div className="flex flex-wrap gap-4">
        <div className="w-full sm:w-48">
          <Field id="perf-days" label="Período">
            {() => (
              <Select
                id="perf-days"
                value={days}
                onValueChange={setDays}
                options={[
                  { value: "7", label: "Últimos 7 dias" },
                  { value: "30", label: "Últimos 30 dias" },
                  { value: "90", label: "Últimos 90 dias" },
                ]}
              />
            )}
          </Field>
        </div>
        <div className="w-full sm:w-72">
          <Field id="perf-subject" label="Disciplina">
            {() => (
              <Select
                id="perf-subject"
                value={subject}
                onValueChange={(v) => {
                  setSubject(v);
                  setDay(null);
                }}
                options={[{ value: "all", label: "Todas as disciplinas" }, ...subjects.current]}
              />
            )}
          </Field>
        </div>
      </div>

      {metrics.error && (
        <p role="alert" className="text-sm text-destructive-text">
          {metrics.error}
        </p>
      )}
      {!m ? (
        <p className="text-sm text-muted-foreground">Carregando…</p>
      ) : (
        <div className={cn("space-y-6 transition-opacity", metrics.loading && "opacity-60")}>
          <section aria-label="Números do período" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi
              label="Horas estudadas"
              value={formatDuration(m.totals.seconds)}
              hint={`${m.totals.study_days} dia(s) com estudo · sequência de ${m.totals.streak}`}
            />
            <Kpi
              label="Testes feitos"
              value={String(m.totals.sets)}
              hint={`${m.totals.questions} questões respondidas · ${m.totals.cards_reviewed} card(s) revisados`}
            />
            <Kpi label="Acerto médio" value={pct(m.totals.accuracy)} hint="em todas as questões do período" />
            <Kpi
              label="Foco no cronômetro"
              value={pct(m.timer.focus)}
              hint={
                m.timer.sessions
                  ? `${m.timer.sessions} sessão(ões) · ${m.timer.average_pauses?.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} pausas em média`
                  : "nenhuma sessão finalizada"
              }
            />
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardContent className="space-y-3">
                <CardEyebrow>Horas por dia</CardEyebrow>
                <HoursChart
                  daily={m.daily}
                  selected={day}
                  coarse={coarse}
                  // No toque, escolher o mesmo dia no Select não fecha o card (só o clique na barra alterna)
                  onSelect={(d) => setDay(d === day && !coarse ? null : d)}
                />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="space-y-3">
                <CardEyebrow>Notas dos testes</CardEyebrow>
                <ScoresChart scores={m.scores} threshold={0.7} onOpen={open} coarse={coarse} />
              </CardContent>
            </Card>
          </section>
          {day && <DayCard day={day} subjectId={subject} onOpen={open} onClose={() => setDay(null)} />}

          <section aria-labelledby="h-por-disciplina" className="space-y-3">
            <h2 id="h-por-disciplina" className="text-lg font-semibold">
              Por disciplina
            </h2>
            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {m.by_subject
                .filter((s) => subject === "all" || String(s.subject_id) === subject)
                .map((s) => (
                  <Card key={s.subject_id}>
                    <CardContent className="space-y-3">
                      <h3 className="text-base font-semibold">{s.name}</h3>
                      <dl className="grid grid-cols-3 gap-3">
                        <div>
                          <dt className="text-xs text-muted-foreground">horas</dt>
                          <dd className="text-sm font-semibold tabular-nums">{formatDuration(s.seconds)}</dd>
                        </div>
                        <div>
                          <dt className="text-xs text-muted-foreground">testes</dt>
                          <dd className="text-sm font-semibold tabular-nums">{s.sets}</dd>
                        </div>
                        <div>
                          <dt className="text-xs text-muted-foreground">nota média</dt>
                          <dd className="text-sm font-semibold tabular-nums">{pct(s.average_score)}</dd>
                        </div>
                      </dl>
                      <InlineMeter
                        label={`Temas aprendidos: ${s.topics_learned} de ${s.topics_total}`}
                        value={s.topics_total ? (s.topics_learned / s.topics_total) * 100 : 0}
                      />
                      <p className="text-xs text-muted-foreground">
                        {s.topics_review} tema(s) para revisar
                        {mistakeSummary(s.mistakes) && ` · erros: ${mistakeSummary(s.mistakes)}`}
                      </p>
                    </CardContent>
                  </Card>
                ))}
            </div>
          </section>

          <section className="grid gap-4 xl:grid-cols-2">
            <TimerSessionsCard />
            <Card>
              <CardContent className="space-y-3">
                <CardEyebrow>Notas de provas, labs e simulados</CardEyebrow>
                {m.graded.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Nenhuma nota lançada ainda (Provas e prazos › Resultado).
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {m.graded.map((g, i) => (
                      <li key={i} className="flex items-center gap-3 py-2 text-sm">
                        <CategoryBadge className="bg-muted text-foreground">{g.kind}</CategoryBadge>
                        <span className="min-w-0 flex-1 truncate">{g.title}</span>
                        <span className="font-semibold tabular-nums">
                          {g.score.toLocaleString("pt-BR")}
                          <span className="text-xs font-normal text-muted-foreground">
                            {" "}
                            de {g.max_score.toLocaleString("pt-BR")}
                          </span>
                        </span>
                        {g.wrong_attempts ? (
                          <span className="text-xs text-muted-foreground">{g.wrong_attempts} erro(s)</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </section>
        </div>
      )}
    </div>
  );
}
