import { Button } from "@/components/ui/button";
import { Card, CardContent, CardEyebrow } from "@/components/ui/card";
import type { NextActionAny, Overview } from "@/lib/api";
import {
  formatDayMonth,
  formatDuration,
  formatNumber,
  formatTime,
  formatWeekdayShort,
  parseLocalDate,
  parseLocalDateTime,
  relativeDays,
} from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CSSProperties } from "react";

/** Próxima prova: dias que faltam + as provas seguintes */
export function NextExamCard({ exams }: { exams: Overview["upcoming_exams"] }) {
  const [first, ...rest] = exams;
  return (
    <Card>
      <CardContent className="space-y-2">
        <CardEyebrow>Próxima prova</CardEyebrow>
        {!first ? (
          <p className="text-sm text-muted-foreground">Nenhuma prova marcada.</p>
        ) : (
          <>
            <p className="text-2xl font-semibold tabular-nums">
              {first.days_left === 0 ? "Hoje" : `${first.days_left} ${first.days_left === 1 ? "dia" : "dias"}`}
              {first.days_left > 0 && <span className="text-sm font-normal text-muted-foreground"> faltam</span>}
            </p>
            <p className="text-sm">
              <span className="font-medium">{first.subject_name}</span>
              {first.scheduled_at ? (
                <span className="text-muted-foreground">
                  {" "}
                  · {formatDayMonth(parseLocalDateTime(first.scheduled_at))} às{" "}
                  {formatTime(parseLocalDateTime(first.scheduled_at))}
                  {first.location ? ` · ${first.location}` : ""}
                </span>
              ) : (
                <span className="text-muted-foreground">
                  {" "}
                  · agendar até {formatDayMonth(parseLocalDate(first.schedule_by!))}
                </span>
              )}
            </p>
            {rest.length > 0 && (
              <p className="text-xs text-muted-foreground">
                Depois:{" "}
                {rest
                  .slice(0, 3)
                  .map((e) =>
                    e.scheduled_at
                      ? `${e.subject_name} ${formatDayMonth(parseLocalDateTime(e.scheduled_at))} ${formatTime(parseLocalDateTime(e.scheduled_at))}`
                      : `${e.subject_name} (agendar até ${formatDayMonth(parseLocalDate(e.schedule_by!))})`,
                  )
                  .join(" · ")}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** Horas na semana contra a meta, com barras por dia (segunda a domingo) */
export function WeekHoursCard({ week, today }: { week: Overview["week"]; today: string }) {
  const max = Math.max(1, ...week.days.map((d) => d.seconds));
  const goalSeconds = week.goal_hours ? week.goal_hours * 3600 : null;
  const pct = goalSeconds ? Math.min(100, (week.total_seconds / goalSeconds) * 100) : null;
  return (
    <Card>
      <CardContent className="space-y-3">
        <CardEyebrow>Horas na semana</CardEyebrow>
        <p className="text-2xl font-semibold tabular-nums">
          {formatDuration(week.total_seconds)}
          <span className="text-sm font-normal text-muted-foreground">
            {week.goal_hours ? ` de ${formatNumber(week.goal_hours, 1)}h` : " · meta não definida"}
          </span>
        </p>
        {pct !== null && (
          <div
            role="meter"
            aria-label="Horas da semana em relação à meta"
            aria-valuenow={Math.round(pct)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuetext={`${Math.round(pct)}% da meta semanal`}
            className="h-2 rounded-full bg-muted"
            style={{ "--value": `${pct}%` } as CSSProperties}
          >
            <div className="h-2 w-[var(--value)] rounded-full bg-primary" />
          </div>
        )}
        <ul className="grid grid-cols-7 gap-2" aria-label="Horas por dia">
          {week.days.map((d) => {
            const date = parseLocalDate(d.date);
            return (
              <li key={d.date} className="flex flex-col items-center gap-1">
                <div className="flex h-10 w-full items-end" aria-hidden="true">
                  <div
                    className={cn("w-full rounded-sm", d.seconds > 0 ? "bg-primary" : "bg-muted")}
                    style={{ height: `${Math.max(4, (d.seconds / max) * 40)}px` }}
                  />
                </div>
                <span
                  className={cn("text-xs", d.date === today ? "font-medium text-foreground" : "text-muted-foreground")}
                >
                  {formatWeekdayShort(date).slice(0, 3)}
                </span>
                <span className="sr-only">{formatDuration(d.seconds)}</span>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}

/** Próxima ação sugerida: reteste vencido primeiro; senão, prova mais próxima e menor progresso */
export function NextActionCard({
  action,
  cardsDue = 0,
  onCards,
}: {
  action: NextActionAny | null;
  cardsDue?: number;
  onCards?: () => void;
}) {
  return (
    <Card>
      <CardContent className="space-y-2">
        <CardEyebrow>Próxima ação sugerida</CardEyebrow>
        {!action ? (
          <p className="text-sm text-muted-foreground">Nada pendente nas disciplinas com prova marcada.</p>
        ) : (
          <>
            <p className="text-sm">
              <span className="font-medium">{action.subject_name}:</span> {sentence(action.steps)}.
            </p>
            {action.kind === "review" ? (
              <p className="text-xs text-muted-foreground">
                {action.reviews_due === 1 ? "1 reteste vencido" : `${action.reviews_due} retestes vencidos`} · desde{" "}
                {formatDayMonth(parseLocalDate(action.due_date))}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                {action.exam_scheduled ? "Prova" : "Agendar até"} {formatDayMonth(parseLocalDate(action.exam_date))} ·{" "}
                {relativeDays(action.exam_days_left)}
                {action.percent !== null && ` · ${Math.round(action.percent)}% no portal`}
              </p>
            )}
            {action.after && (
              <p className="text-xs text-muted-foreground">
                Depois: {action.after.subject_name} ({formatDayMonth(parseLocalDate(action.after.exam_date))})
              </p>
            )}
          </>
        )}
        {cardsDue > 0 && (
          // v1.6 (D35): cards vencidos hoje junto da próxima ação
          <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
            {cardsDue === 1 ? "1 card para revisar hoje" : `${cardsDue} cards para revisar hoje`}
            {onCards && (
              <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={onCards}>
                Revisar agora
              </Button>
            )}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function sentence(steps: string[]): string {
  if (steps.length === 0) return "";
  const text = steps.length === 1 ? steps[0] : `${steps.slice(0, -1).join(", ")} e ${steps[steps.length - 1]}`;
  return text.charAt(0).toUpperCase() + text.slice(1);
}
