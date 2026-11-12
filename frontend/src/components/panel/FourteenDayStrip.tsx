import { CalendarDays, ClipboardCheck, Clock, type LucideIcon } from "lucide-react";

import { Card, CardContent, CardTitle } from "@/components/ui/card";
import type { TimelineItem } from "@/lib/api";
import { formatDayMonth, formatLongDate, formatWeekdayShort, parseLocalDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const CATEGORY: Record<TimelineItem["category"], { icon: LucideIcon; label: string }> = {
  exam: { icon: ClipboardCheck, label: "Prova" },
  deadline: { icon: Clock, label: "Prazo" },
  event: { icon: CalendarDays, label: "Evento" },
};

function cellLabel(date: Date, items: TimelineItem[], isToday: boolean) {
  const base = (isToday ? "Hoje, " : "") + formatLongDate(date);
  if (items.length === 0) return `${base}: sem eventos`;
  return `${base}: ${items.map((i) => i.title + (i.time ? ` às ${i.time}` : "")).join("; ")}`;
}

/** Faixa de 14 dias (DS v2.13). Células não interativas; abaixo de sm vira lista só com os dias com evento. */
export function FourteenDayStrip({ days, today }: { days: { date: string; items: TimelineItem[] }[]; today: string }) {
  const withEvents = days.filter((d) => d.items.length > 0);
  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex items-baseline justify-between gap-4">
          <CardTitle>Próximos 14 dias</CardTitle>
          {days.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {formatDayMonth(parseLocalDate(days[0].date))} a {formatDayMonth(parseLocalDate(days[days.length - 1].date))}
            </p>
          )}
        </div>

        <ol className="hidden gap-2 sm:grid sm:grid-cols-14">
          {days.map(({ date, items }) => {
            const d = parseLocalDate(date);
            const isToday = date === today;
            return (
              <li
                key={date}
                aria-current={isToday ? "date" : undefined}
                aria-label={cellLabel(d, items, isToday)}
                className={cn(
                  "flex min-h-20 flex-col items-center gap-1 rounded-md border p-2",
                  isToday ? "border-primary" : "border-transparent",
                )}
              >
                <span aria-hidden="true" className="text-xs text-muted-foreground">
                  {formatWeekdayShort(d)}
                </span>
                <span aria-hidden="true" className="text-sm">
                  {d.getDate()}
                </span>
                <span aria-hidden="true" className="flex flex-wrap justify-center gap-1">
                  {items.map((item, idx) => {
                    const Icon = CATEGORY[item.category].icon;
                    return <Icon key={`${item.category}-${idx}`} className="h-3 w-3 text-foreground" />;
                  })}
                </span>
              </li>
            );
          })}
        </ol>

        <ul className="space-y-3 sm:hidden">
          {withEvents.length === 0 && <li className="text-sm text-muted-foreground">Nenhum evento nos próximos 14 dias.</li>}
          {withEvents.map(({ date, items }) => {
            const d = parseLocalDate(date);
            return (
              <li key={date} aria-current={date === today ? "date" : undefined}>
                <p className="text-sm font-medium">
                  {date === today ? "Hoje, " : ""}
                  {formatLongDate(d)}
                </p>
                <ul className="mt-1 space-y-1">
                  {items.map((item, idx) => {
                    const Icon = CATEGORY[item.category].icon;
                    return (
                      <li key={`${item.category}-${idx}`} className="flex items-center gap-2 text-sm">
                        <Icon className="h-3 w-3 shrink-0 text-foreground" aria-hidden="true" />
                        <span className="sr-only">{CATEGORY[item.category].label}: </span>
                        {item.title}
                        {item.time && <span className="text-muted-foreground"> · {item.time}</span>}
                      </li>
                    );
                  })}
                </ul>
              </li>
            );
          })}
        </ul>

        <ul aria-label="Legenda" className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          {Object.values(CATEGORY).map(({ icon: Icon, label }) => (
            <li key={label} className="flex items-center gap-1">
              <Icon className="h-3 w-3 text-foreground" aria-hidden="true" />
              {label}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
