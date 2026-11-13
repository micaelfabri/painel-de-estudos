import * as React from "react";

import { CategoryBadge } from "@/components/ui/badge";
import { Button, focusRing } from "@/components/ui/button";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import type { TimelineItem } from "@/lib/api";
import { formatDayMonth, formatLongDate, formatWeekdayShort, parseLocalDate } from "@/lib/format";
import { cn } from "@/lib/utils";

// Proposta aprovada pelo dono em 12/11/2026:
// contagens por tipo em cada dia, duas semanas, clique no dia abre a lista com horários.
const CATEGORY: Record<
  TimelineItem["category"],
  { one: string; many: string; label: string; chip: string; dot: string }
> = {
  exam: {
    one: "prova",
    many: "provas",
    label: "Prova",
    chip: "bg-primary/10 font-semibold text-primary-text",
    dot: "bg-primary",
  },
  deadline: {
    one: "prazo",
    many: "prazos",
    label: "Prazo, lab, atividade ou simulado",
    chip: "bg-warning/10 text-foreground",
    dot: "bg-warning",
  },
  event: {
    one: "evento",
    many: "eventos",
    label: "Evento da agenda",
    chip: "text-muted-foreground",
    dot: "bg-muted-foreground",
  },
};
const ORDER: TimelineItem["category"][] = ["exam", "deadline", "event"];

function counts(items: TimelineItem[]) {
  return ORDER.map((cat) => ({ cat, n: items.filter((i) => i.category === cat).length })).filter((c) => c.n > 0);
}

function dayLabel(date: Date, items: TimelineItem[], isToday: boolean) {
  const base = (isToday ? "Hoje, " : "") + formatLongDate(date);
  if (items.length === 0) return `${base}: nada marcado`;
  return `${base}: ${counts(items)
    .map(({ cat, n }) => `${n} ${n === 1 ? CATEGORY[cat].one : CATEGORY[cat].many}`)
    .join(", ")}`;
}

function sortItems(items: TimelineItem[]) {
  return [...items].sort((a, b) => (a.time ?? "99").localeCompare(b.time ?? "99"));
}

// v1.5.1: dia cheio (ex.: 19/11 com 10 simulados) mostra os 5 primeiros e "Ver mais"
const SHORT_LIST = 5;

/** Lista de um dia, com horário, tipo e itens feitos riscados */
function DayList({ items }: { items: TimelineItem[] }) {
  const [all, setAll] = React.useState(false);
  if (items.length === 0) return <p className="text-sm text-muted-foreground">Nada marcado neste dia.</p>;
  const sorted = sortItems(items);
  const long = sorted.length > SHORT_LIST + 1;
  const shown = long && !all ? sorted.slice(0, SHORT_LIST) : sorted;
  return (
    <div className="space-y-1">
      <ul className="divide-y divide-border">
        {shown.map((item, idx) => (
          <li key={`${item.category}-${idx}`} className="flex items-center gap-3 py-2 text-sm">
            <span className="w-12 shrink-0 tabular-nums text-muted-foreground">{item.time ?? "—"}</span>
            <span className={cn("min-w-0 flex-1", item.done && "text-muted-foreground line-through")}>
              {item.title}
              {item.done && <span className="sr-only"> (feito)</span>}
            </span>
            <CategoryBadge className={cn("shrink-0", CATEGORY[item.category].chip)}>
              {item.label ?? CATEGORY[item.category].label.split(",")[0]}
            </CategoryBadge>
          </li>
        ))}
      </ul>
      {long && (
        <Button variant="ghost" size="sm" onClick={() => setAll((v) => !v)} aria-expanded={all}>
          {all ? "Mostrar menos" : `Ver mais ${sorted.length - SHORT_LIST}`}
        </Button>
      )}
    </div>
  );
}

/** Faixa de 14 dias: duas linhas de 7 dias; abaixo de sm, lista dos dias com algo marcado */
export function FourteenDayStrip({ days, today }: { days: { date: string; items: TimelineItem[] }[]; today: string }) {
  const [selected, setSelected] = React.useState(today);
  const withItems = days.filter((d) => d.items.length > 0);
  const current = days.find((d) => d.date === selected) ?? days[0];
  const weeks = [days.slice(0, 7), days.slice(7, 14)];

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex items-baseline justify-between gap-4">
          <CardTitle>Próximos 14 dias</CardTitle>
          {days.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {formatDayMonth(parseLocalDate(days[0].date))} a{" "}
              {formatDayMonth(parseLocalDate(days[days.length - 1].date))}
            </p>
          )}
        </div>

        <div className="hidden space-y-2 sm:block">
          {weeks.map((week, w) => (
            <div key={w} className="space-y-2">
              <p className="text-xs text-muted-foreground">{w === 0 ? "Esta semana" : "Próxima semana"}</p>
              <ol className="grid grid-cols-7 gap-2">
                {week.map(({ date, items }) => {
                  const d = parseLocalDate(date);
                  const isToday = date === today;
                  const isSelected = date === current?.date;
                  return (
                    <li key={date}>
                      <button
                        type="button"
                        onClick={() => setSelected(date)}
                        aria-pressed={isSelected}
                        aria-current={isToday ? "date" : undefined}
                        aria-label={dayLabel(d, items, isToday)}
                        className={cn(
                          "flex h-full min-h-24 w-full flex-col gap-1 rounded-md border p-2 text-left transition-colors duration-150 hover:bg-muted",
                          isToday ? "border-primary" : "border-border",
                          isSelected && "bg-muted hover:bg-muted",
                          focusRing,
                        )}
                      >
                        <span aria-hidden="true" className="flex items-baseline justify-between">
                          <span className={cn("text-xs", "text-muted-foreground")}>{formatWeekdayShort(d)}</span>
                          <span className="text-base font-semibold tabular-nums">{d.getDate()}</span>
                        </span>
                        {counts(items).map(({ cat, n }) => (
                          <span
                            key={cat}
                            aria-hidden="true"
                            className={cn("flex items-start gap-1 rounded-md px-1 py-0.5 text-xs", CATEGORY[cat].chip)}
                          >
                            <span className={cn("mt-1 h-2 w-2 shrink-0 rounded-full", CATEGORY[cat].dot)} />
                            <span className="leading-tight">
                              {n} {n === 1 ? CATEGORY[cat].one : CATEGORY[cat].many}
                            </span>
                          </span>
                        ))}
                      </button>
                    </li>
                  );
                })}
              </ol>
            </div>
          ))}

          <ul aria-label="Legenda" className="flex flex-wrap gap-4 pt-2 text-xs text-muted-foreground">
            {ORDER.map((cat) => (
              <li key={cat} className="flex items-center gap-1.5">
                <span className={cn("h-2 w-2 rounded-full", CATEGORY[cat].dot)} aria-hidden="true" />
                {CATEGORY[cat].label}
              </li>
            ))}
          </ul>

          {current && (
            <section aria-live="polite" className="space-y-2 border-t border-border pt-4">
              <h3 className="text-sm font-semibold">
                {current.date === today ? "Hoje · " : ""}
                {formatLongDate(parseLocalDate(current.date))}
              </h3>
              <DayList key={current.date} items={current.items} />
            </section>
          )}
        </div>

        <ul className="space-y-4 sm:hidden">
          {withItems.length === 0 && (
            <li className="text-sm text-muted-foreground">Nada marcado nos próximos 14 dias.</li>
          )}
          {withItems.map(({ date, items }) => (
            <li key={date} aria-current={date === today ? "date" : undefined} className="space-y-1">
              <p className="text-sm font-medium">
                {date === today ? "Hoje, " : ""}
                {formatLongDate(parseLocalDate(date))}
              </p>
              <DayList items={items} />
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
