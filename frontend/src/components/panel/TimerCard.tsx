import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardEyebrow } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import type { CourseModuleOption } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatDuration } from "@/lib/format";
import { TimerRing } from "./TimerRing";
import { useStudyTimer } from "./useStudyTimer";

interface TimerCardProps {
  subjects: { id: number; name: string }[];
  goalMinutes: number;
  alarmMinutes: number;
  onSaved: () => void;
}

/** Cronômetro de estudo: meta por tema e alarme vêm das configurações */
export function TimerCard({ subjects, goalMinutes, alarmMinutes, onSaved }: TimerCardProps) {
  // v1.8 (D41): módulos dos cursos em andamento depois das disciplinas da faculdade
  // (o Select do padrão de design ainda não tem grupos; por ora o rótulo começa com "Curso:")
  const modules = useApi<CourseModuleOption[]>("/courses/modules");
  const timer = useStudyTimer(
    goalMinutes,
    alarmMinutes,
    (seconds) => {
      toast.success(`Trecho de ${seconds < 60 ? `${seconds} s` : formatDuration(seconds)} salvo`);
      onSaved();
    },
    (t) => {
      // Resumo da sessão: tempo estudado, tempo total (relógio oculto) e pausas (D24)
      toast.success(
        `Sessão finalizada: ${formatDuration(t.active_seconds)} estudados` +
          `${t.wall_seconds ? ` em ${formatDuration(t.wall_seconds)} no total` : ""}, ${t.pauses} pausa(s).`,
      );
      onSaved();
    },
    () => {
      toast.success("Sessão cancelada: nada foi salvo.");
      setLiveMsg("Sessão descartada");
      onSaved();
    },
  );
  const [confirmCancel, setConfirmCancel] = React.useState(false);
  const [liveMsg, setLiveMsg] = React.useState("");
  React.useEffect(() => {
    if (timer.running) setLiveMsg("");
  }, [timer.running]);

  const handle = (fn: () => Promise<void> | void) => async () => {
    try {
      await fn();
    } catch {
      toast.error("Não foi possível salvar a sessão. O tempo continua no cronômetro.");
    }
  };

  return (
    <Card>
      <CardContent className="space-y-4">
        <CardEyebrow>Cronômetro de estudo</CardEyebrow>
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
          <TimerRing elapsed={timer.elapsed} goal={timer.goal} status={timer.status} />
          <div className="flex w-full flex-1 flex-col gap-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="timer-subject">Disciplina</Label>
              <Select
                id="timer-subject"
                value={timer.subjectId === null ? "none" : String(timer.subjectId)}
                onValueChange={(v) => timer.setSubject(v === "none" ? null : Number(v))}
                options={[
                  { value: "none", label: "Sem disciplina" },
                  ...subjects.map((s) => ({ value: String(s.id), label: s.name })),
                  ...(modules.data ?? []).map((m) => ({
                    value: String(m.id),
                    label: `Curso: ${m.course_name} · ${m.name}`,
                  })),
                ]}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Meta de {formatDuration(goalMinutes * 60)} por tema, alarme em {formatDuration(alarmMinutes * 60)}. Cada
              pausa salva o trecho estudado; Finalizar fecha a sessão com o tempo total e as pausas; Cancelar descarta a
              sessão.
            </p>
            <p className="sr-only" aria-live="polite">
              {liveMsg}
            </p>
            {timer.status !== "idle" && (
              <p className="text-xs text-muted-foreground" aria-live="polite">
                {timer.pauses} {timer.pauses === 1 ? "pausa" : "pausas"} nesta sessão
              </p>
            )}
            <div className="flex flex-wrap gap-3">
              {timer.running ? (
                <Button onClick={handle(timer.pause)}>Pausar</Button>
              ) : (
                <Button onClick={handle(timer.start)}>Iniciar</Button>
              )}
              {/* Resposta 06 do DS: Finalizar e Cancelar desativados enquanto o tempo é 0 */}
              <Button variant="secondary" onClick={handle(timer.finish)} disabled={timer.elapsed === 0}>
                Finalizar
              </Button>
              <Button variant="outline" onClick={() => setConfirmCancel(true)} disabled={timer.elapsed === 0}>
                Cancelar
              </Button>
            </div>
            <ConfirmDialog
              open={confirmCancel}
              onOpenChange={setConfirmCancel}
              title="Cancelar esta sessão?"
              note={`O tempo desta sessão (${timer.elapsed < 60 ? `${timer.elapsed} s` : formatDuration(timer.elapsed)}) não fica salvo: sai das horas estudadas e da lista de sessões. Não dá para desfazer. Para guardar o tempo, use Finalizar.`}
              confirmLabel="Descartar sessão"
              cancelLabel="Voltar ao cronômetro"
              destructive
              onConfirm={timer.cancel}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
