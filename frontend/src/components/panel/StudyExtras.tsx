import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { CategoryBadge } from "@/components/ui/badge";
import { focusRing } from "@/components/ui/button";
import { Card, CardContent, CardEyebrow } from "@/components/ui/card";
import type { AgendaItem, WeekSummary } from "@/lib/api";
import { formatDayMonth, formatDuration, parseLocalDate } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Resumo da semana (SPEC D20): horas, testes, nota média, temas aprendidos e itens feitos */
export function WeekSummaryCard({ week }: { week: WeekSummary | null }) {
  const stats: [string, string][] = week
    ? [
        ["estudadas", formatDuration(week.seconds)],
        ["testes feitos", String(week.sets)],
        ["nota média", week.average_score === null ? "—" : `${Math.round(week.average_score * 100)}%`],
        ["temas aprendidos", String(week.topics_learned)],
        ["provas e prazos feitos", String(week.items_done)],
      ]
    : [];
  return (
    <Card>
      <CardContent className="space-y-3">
        <CardEyebrow>Resumo da semana</CardEyebrow>
        {!week ? (
          <p className="text-sm text-muted-foreground">Carregando…</p>
        ) : (
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {stats.map(([label, value]) => (
              <div key={label} className="min-w-0">
                <dt className="break-words text-xs text-muted-foreground">{label}</dt>
                <dd className="text-lg font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </CardContent>
    </Card>
  );
}

/** Pendências no painel: próximas provas, prazos, laboratórios e atividades não feitos (SPEC D13) */
export function PendingCard({ items, today }: { items: AgendaItem[]; today: string }) {
  const pending = items.filter((i) => !i.done).slice(0, 6);
  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <CardEyebrow>Pendências</CardEyebrow>
          <Link
            to="/estudo/provas"
            className={cn(
              "inline-flex items-center gap-1 rounded-md text-xs font-medium text-primary-text hover:underline",
              focusRing,
            )}
          >
            Provas e prazos
            <ArrowRight className="h-3 w-3" aria-hidden="true" />
          </Link>
        </div>
        {pending.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nada pendente.</p>
        ) : (
          <ul className="space-y-2">
            {pending.map((i) => {
              const late = i.date !== null && i.date < today;
              return (
                <li key={`${i.type}-${i.id}`} className="flex items-center gap-2 text-sm">
                  <CategoryBadge className={late ? "bg-warning/10 text-warning-text" : "bg-muted text-foreground"}>
                    {i.kind_label}
                  </CategoryBadge>
                  <span className="min-w-0 flex-1 truncate">{i.title}</span>
                  <span
                    className={cn(
                      "shrink-0 text-xs tabular-nums",
                      late ? "text-warning-text" : "text-muted-foreground",
                    )}
                  >
                    {i.date ? `${late ? "atrasado · " : ""}${formatDayMonth(parseLocalDate(i.date))}` : "sem data"}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
