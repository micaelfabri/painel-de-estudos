import { ArrowRight, CheckCircle2, Circle } from "lucide-react";

import { formatDayMonth, formatDuration, parseLocalDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export type DayTask = {
  id: number;
  label: string;
  done: boolean;
  planned_minutes: number | null;
  /** D49: não feita neste dia e passada para outro */
  carried_to?: string | null;
  /** D49: veio de um dia anterior (primeiro dia da cadeia) */
  started_on?: string | null;
};

const dm = (iso: string) => formatDayMonth(parseLocalDate(iso));

/** Feita, passada para outro dia (rastro) ou não feita; "começou em" quando veio de outro dia */
function status(t: DayTask): string {
  if (t.done) return t.started_on ? `feita · começou em ${dm(t.started_on)}` : "feita";
  if (t.carried_to) return `passou para ${dm(t.carried_to)}`;
  return t.started_on ? `não feita · começou em ${dm(t.started_on)}` : "não feita";
}

/** Tarefas de um dia (Desempenho › dia e Histórico › Tarefas por dia) */
export function DayTaskList({ tasks }: { tasks: DayTask[] }) {
  return (
    <ul className="divide-y divide-border text-sm">
      {tasks.map((t) => (
        <li key={t.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
          {t.done ? (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-success-text" aria-hidden="true" />
          ) : t.carried_to ? (
            <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          ) : (
            <Circle className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          )}
          <span
            className={cn(
              "min-w-0 flex-1",
              t.done && "text-muted-foreground line-through",
              t.carried_to && "text-muted-foreground",
            )}
          >
            {t.label}
          </span>
          {t.planned_minutes ? (
            <span className="tabular-nums text-muted-foreground">{formatDuration(t.planned_minutes * 60)}</span>
          ) : null}
          <span className="shrink-0 text-right text-xs text-muted-foreground">{status(t)}</span>
        </li>
      ))}
    </ul>
  );
}
