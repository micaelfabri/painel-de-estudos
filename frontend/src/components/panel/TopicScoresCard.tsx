import { AlertTriangle } from "lucide-react";

import { Card, CardContent, CardTitle } from "@/components/ui/card";
import type { TopicScore } from "@/lib/api";
import { formatDayMonth, parseLocalDate } from "@/lib/format";
import { InlineMeter } from "./InlineMeter";

const pct = (v: number | null) => (v === null ? 0 : Math.round(v * 100));

/**
 * Acerto nas questões por tema (SPEC §6.3). O limiar de 70% só vale para o reteste que decide
 * (7 dias ou revisão); antes dele, o medidor mostra a primeira nota sem limiar.
 */
export function TopicScoresCard({ topics, threshold }: { topics: TopicScore[]; threshold: number }) {
  return (
    <Card>
      <CardContent className="space-y-4">
        <CardTitle>Acerto nas questões por tema</CardTitle>
        {topics.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum conjunto de questões concluído ainda. Use "Gerar questões" no agente.
          </p>
        ) : (
          <ul className="space-y-4">
            {topics.map((t) => {
              const decisive = t.decisive_score !== null;
              const value = decisive ? pct(t.decisive_score) : pct(t.first_score ?? t.last_score);
              const label = `${t.subject_name} · ${t.topic_title}`;
              return (
                <li key={t.topic_id} className="space-y-1">
                  <p className="text-sm">{label}</p>
                  <InlineMeter
                    label={label}
                    hideLabel
                    value={value}
                    threshold={decisive ? Math.round(threshold * 100) : undefined}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t.status === "review" && (
                      <span className="mr-1 inline-flex items-center gap-1 text-warning-text">
                        <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                        Revisar ·
                      </span>
                    )}
                    {decisive ? `Reteste que decide: ${value}%` : `1ª nota: ${value}%`}
                    {t.next_review && ` · ${t.next_review.label} em ${formatDayMonth(parseLocalDate(t.next_review.date))}`}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
