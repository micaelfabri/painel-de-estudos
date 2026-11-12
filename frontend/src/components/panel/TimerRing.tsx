import { AlarmClock, Target } from "lucide-react";
import * as React from "react";

import { formatClock, formatDuration } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TimerState } from "./useStudyTimer";

const SIZE = 160;
const STROKE = 8;
const RADIUS = (SIZE - STROKE) / 2;
const CIRC = 2 * Math.PI * RADIUS;

const STROKE_CLASS: Record<TimerState, string> = {
  idle: "stroke-primary",
  running: "stroke-primary",
  paused: "stroke-muted-foreground",
  past_goal: "stroke-warning",
  alarm: "stroke-warning",
};

function stateText(status: TimerState, elapsed: number, goal: number): string {
  switch (status) {
    case "idle":
      return "Parado";
    case "running":
      return "Rodando";
    case "paused":
      return "Pausado";
    case "past_goal":
      return `Passou da meta · +${Math.floor((elapsed - goal) / 60)} min`;
    case "alarm":
      return "Alarme";
  }
}

/** Anel do cronômetro (DS v2.13): estado sempre em texto, SVG escondido do leitor de tela */
export function TimerRing({ elapsed, goal, status }: { elapsed: number; goal: number; status: TimerState }) {
  const progress = Math.min(1, goal > 0 ? elapsed / goal : 0);
  const text = stateText(status, elapsed, goal);

  // Anuncia só mudanças de estado, nunca a cada segundo
  const [announcement, setAnnouncement] = React.useState("");
  const previous = React.useRef<TimerState>(status);
  React.useEffect(() => {
    if (previous.current !== status) {
      const messages: Partial<Record<TimerState, string>> = {
        running: "Cronômetro iniciado",
        paused: "Cronômetro pausado",
        past_goal: "Meta atingida",
        alarm: "Alarme do cronômetro",
        idle: "Cronômetro zerado",
      };
      setAnnouncement(messages[status] ?? "");
      previous.current = status;
    }
  }, [status]);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-40 w-40">
        {/* Trilha em --border nos dois modos (resposta do DS ao pedido 02) */}
        <svg aria-hidden="true" viewBox={`0 0 ${SIZE} ${SIZE}`} className="h-40 w-40 -rotate-90">
          <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" strokeWidth={STROKE} className="stroke-border" />
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={CIRC * (1 - progress)}
            className={cn("transition-[stroke-dashoffset] duration-200 motion-reduce:transition-none", STROKE_CLASS[status])}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span role="timer" className="text-2xl font-semibold tabular-nums">
            {formatClock(elapsed)}
          </span>
          <span className="text-xs text-muted-foreground">de {formatDuration(goal)}</span>
        </div>
      </div>
      <p className="flex items-center gap-1 text-sm">
        {status === "past_goal" && <Target className="h-4 w-4 text-warning-text" aria-hidden="true" />}
        {status === "alarm" && <AlarmClock className="h-4 w-4 text-warning-text" aria-hidden="true" />}
        <span className={cn(status === "past_goal" || status === "alarm" ? "text-warning-text" : "text-muted-foreground")}>
          {text}
        </span>
      </p>
      <div aria-live="polite" className="sr-only">
        {announcement}
      </div>
    </div>
  );
}
