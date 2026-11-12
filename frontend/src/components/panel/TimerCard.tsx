import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardEyebrow } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import type { SubjectOverview } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import { TimerRing } from "./TimerRing";
import { useStudyTimer } from "./useStudyTimer";

interface TimerCardProps {
  subjects: SubjectOverview[];
  goalMinutes: number;
  alarmMinutes: number;
  onSaved: () => void;
}

/** Cronômetro de estudo: meta por tema e alarme vêm das configurações */
export function TimerCard({ subjects, goalMinutes, alarmMinutes, onSaved }: TimerCardProps) {
  const timer = useStudyTimer(goalMinutes, alarmMinutes, (seconds) => {
    toast.success(`Sessão de ${formatDuration(seconds)} salva`);
    onSaved();
  });

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
                ]}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Meta de {formatDuration(goalMinutes * 60)} por tema, alarme em {formatDuration(alarmMinutes * 60)}. Cada pausa salva
              o trecho estudado.
            </p>
            <div className="flex gap-3">
              {timer.running ? (
                <Button onClick={handle(timer.pause)}>Pausar</Button>
              ) : (
                <Button onClick={handle(timer.start)}>Iniciar</Button>
              )}
              <Button variant="outline" onClick={handle(timer.reset)} disabled={timer.status === "idle"}>
                Zerar
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
