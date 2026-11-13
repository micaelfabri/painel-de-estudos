import { useAgent } from "@/components/agent/AgentContext";
import { Card, CardContent, CardEyebrow } from "@/components/ui/card";
import type { TimerSessionView } from "@/lib/api";
import { formatDayMonth, formatDuration, formatTime, parseLocalDateTime } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import * as React from "react";

/** Sessões do cronômetro (SPEC D24): tempo estudado, tempo total (relógio oculto) e pausas */
export function TimerSessionsCard({ limit = 8, version = 0 }: { limit?: number; version?: number }) {
  const sessions = useApi<TimerSessionView[]>(`/study/timer-sessions?limit=${limit}`);
  const { learningVersion } = useAgent();
  const reload = sessions.reload;
  React.useEffect(() => {
    if (version > 0 || learningVersion > 0) void reload();
  }, [version, learningVersion, reload]);
  const rows = sessions.data ?? [];

  return (
    <Card>
      <CardContent className="space-y-3">
        <CardEyebrow>Sessões do cronômetro</CardEyebrow>
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
      </CardContent>
    </Card>
  );
}
