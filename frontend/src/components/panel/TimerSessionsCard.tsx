import { useAgent } from "@/components/agent/AgentContext";
import { Card, CardContent, CardEyebrow } from "@/components/ui/card";
import type { Area, TimerSessionView } from "@/lib/api";
import { formatDayMonth, formatDuration, formatTime, parseLocalDateTime } from "@/lib/format";
import { PER_PAGE, usePaged } from "@/lib/usePaged";
import { useApi } from "@/lib/useApi";
import { Pagination } from "@/components/ui/pagination";
import * as React from "react";

/**
 * Sessões do cronômetro (SPEC D24): tempo estudado, tempo total (relógio oculto) e pausas.
 * v1.7.2: sem `limit` mostra todas, em páginas de 10 (Desempenho); com `limit`, só as últimas (Painel).
 */
export function TimerSessionsCard({
  limit,
  version = 0,
  area = "faculdade",
}: {
  limit?: number;
  version?: number;
  area?: Area;
}) {
  const sessions = useApi<TimerSessionView[]>(`/study/timer-sessions?limit=${limit ?? 1000}&area=${area}`);
  const { learningVersion } = useAgent();
  const reload = sessions.reload;
  React.useEffect(() => {
    if (version > 0 || learningVersion > 0) void reload();
  }, [version, learningVersion, reload]);
  const paged = usePaged(sessions.data ?? [], null, limit ?? PER_PAGE);
  const rows = paged.slice;

  return (
    <Card>
      <CardContent className="space-y-3">
        <div
          ref={paged.anchor as React.RefObject<HTMLDivElement>}
          tabIndex={-1}
          className="scroll-mt-20 focus:outline-none"
        >
          <CardEyebrow>Sessões do cronômetro</CardEyebrow>
        </div>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma sessão ainda. Use Iniciar e, no fim, Finalizar.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Sessões do cronômetro</caption>
              <thead>
                <tr className="text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-1 pr-3 font-medium">
                    Quando
                  </th>
                  <th scope="col" className="py-1 pr-3 font-medium">
                    Disciplina
                  </th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">
                    Estudado
                  </th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">
                    Total
                  </th>
                  <th scope="col" className="py-1 text-right font-medium">
                    Pausas
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((t) => {
                  const d = parseLocalDateTime(t.started_at);
                  return (
                    <tr key={t.id}>
                      <td className="py-2 pr-3 tabular-nums">
                        {formatDayMonth(d)} {formatTime(d)}
                      </td>
                      <td className="py-2 pr-3">{t.subject_name ?? "—"}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{formatDuration(t.active_seconds)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {t.wall_seconds !== null ? formatDuration(t.wall_seconds) : "em andamento"}
                      </td>
                      <td className="py-2 text-right tabular-nums">{t.pauses}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {limit === undefined && (
          <Pagination
            page={paged.page}
            pages={paged.pages}
            total={paged.total}
            onPage={paged.goTo}
            label="Páginas das sessões do cronômetro"
          />
        )}
      </CardContent>
    </Card>
  );
}
