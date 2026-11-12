import { Calendar } from "lucide-react";

import { CategoryBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { Counter, SubjectOverview } from "@/lib/api";
import { formatDayMonth, formatTime, parseLocalDate, parseLocalDateTime, relativeDays } from "@/lib/format";
import { cn } from "@/lib/utils";
import { InlineMeter } from "./InlineMeter";

function examBadgeText(exam: NonNullable<SubjectOverview["exam"]>): string {
  if (exam.scheduled_at) {
    const d = parseLocalDateTime(exam.scheduled_at);
    return `Prova ${formatDayMonth(d)} ${formatTime(d)}`;
  }
  return `Agendar até ${formatDayMonth(parseLocalDate(exam.schedule_by!))}`;
}

const COUNTER_LABELS: { key: keyof SubjectOverview["counters"]; label: string }[] = [
  { key: "contents", label: "conteúdos" },
  { key: "exercises", label: "exercícios" },
  { key: "mocks", label: "simulados" },
  { key: "lab", label: "laboratório" },
];

/** Card de disciplina (DS v2.13): não é StatCard e não é clicável */
export function SubjectCard({ subject }: { subject: SubjectOverview }) {
  const exam = subject.exam;
  const soon = exam !== null && exam.days_left <= 7;
  const counters = COUNTER_LABELS.filter(({ key }) => subject.counters[key] !== null);

  return (
    <Card className="flex flex-col gap-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-base font-semibold">{subject.name}</h3>
        {exam && (
          <CategoryBadge className={cn("shrink-0", soon ? "bg-warning/10 text-warning-text" : "bg-muted text-muted-foreground")}>
            <Calendar aria-hidden="true" />
            {examBadgeText(exam)}
            {soon && <span>· {relativeDays(exam.days_left)}</span>}
          </CategoryBadge>
        )}
      </div>

      <div>
        <p className="text-2xl font-semibold tabular-nums">
          {subject.percent === null ? "—" : `${Math.round(subject.percent)}%`}
        </p>
        <p className="text-xs text-muted-foreground">progresso no portal</p>
      </div>
      {subject.percent !== null && <InlineMeter label={`Progresso de ${subject.name}`} value={subject.percent} hideLabel />}

      {counters.length > 0 && (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {counters.map(({ key, label }) => {
            const c = subject.counters[key] as Exclude<Counter, null>;
            return (
              <div key={key} className="min-w-0">
                <dt className="break-words text-xs text-muted-foreground">{label}</dt>
                <dd className="text-sm tabular-nums">
                  {c[0]}/{c[1]}
                </dd>
              </div>
            );
          })}
        </dl>
      )}
    </Card>
  );
}
