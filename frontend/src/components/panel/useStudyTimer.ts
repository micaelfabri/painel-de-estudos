import * as React from "react";

import { api } from "@/lib/api";
import { toIsoLocal } from "@/lib/format";
import { playAlarm, playGoal, unlockAudio } from "@/lib/sound";

// Estado do cronômetro guardado no navegador para sobreviver a recarregar a página.
const STORAGE_KEY = "painel.timer.v1";

interface StoredTimer {
  subjectId: number | null;
  running: boolean;
  /** Segundos acumulados antes do trecho atual */
  accumulated: number;
  /** Início do trecho atual (ms), quando rodando */
  chunkStart: number | null;
}

const EMPTY: StoredTimer = { subjectId: null, running: false, accumulated: 0, chunkStart: null };

function load(): StoredTimer {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...EMPTY, ...JSON.parse(raw) } : EMPTY;
  } catch {
    return EMPTY;
  }
}

function save(state: StoredTimer) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* armazenamento indisponível: o cronômetro funciona só em memória */
  }
}

export type TimerState = "idle" | "running" | "paused" | "past_goal" | "alarm";

/**
 * Cronômetro de estudo. Cada trecho entre Iniciar e Pausar vira uma sessão salva
 * na API (SPEC §6.1: cada sessão é salva), então nada se perde ao zerar.
 */
const ALARM_REPEAT = 10 * 60; // segundos entre repetições do alarme

export function useStudyTimer(goalMinutes: number, alarmMinutes: number, onSaved?: (seconds: number) => void) {
  const [state, setState] = React.useState<StoredTimer>(load);
  const [now, setNow] = React.useState(() => Date.now());

  React.useEffect(() => save(state), [state]);

  React.useEffect(() => {
    if (!state.running) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [state.running]);

  const chunkSeconds = state.running && state.chunkStart ? Math.floor((now - state.chunkStart) / 1000) : 0;
  const elapsed = state.accumulated + chunkSeconds;

  const goal = goalMinutes * 60;
  const alarm = alarmMinutes * 60;
  let status: TimerState = "idle";
  if (elapsed > 0 || state.running) {
    if (!state.running) status = "paused";
    else if (elapsed >= alarm) status = "alarm";
    else if (elapsed >= goal) status = "past_goal";
    else status = "running";
  }

  // Som ao cruzar a meta e o alarme; o alarme repete a cada 10 min enquanto o cronômetro roda
  const lastStatus = React.useRef<TimerState>(status);
  const lastAlarmAt = React.useRef(0);
  React.useEffect(() => {
    const prev = lastStatus.current;
    lastStatus.current = status;
    if (status === "past_goal" && prev === "running") playGoal();
    if (status === "alarm") {
      const due = prev !== "alarm" ? prev === "past_goal" || prev === "running" : elapsed - lastAlarmAt.current >= ALARM_REPEAT;
      if (due) {
        lastAlarmAt.current = elapsed;
        playAlarm();
      }
    }
  }, [status, elapsed]);

  const persistChunk = React.useCallback(
    async (start: number, seconds: number, subjectId: number | null) => {
      if (seconds < 1) return;
      await api.post("/study-sessions", {
        subject_id: subjectId,
        started_at: toIsoLocal(new Date(start)),
        ended_at: toIsoLocal(new Date(start + seconds * 1000)),
        seconds,
      });
      onSaved?.(seconds);
    },
    [onSaved],
  );

  const start = () => {
    unlockAudio();
    setNow(Date.now());
    setState((s) => ({ ...s, running: true, chunkStart: Date.now() }));
  };

  const pause = async () => {
    const chunkStart = state.chunkStart ?? Date.now();
    const seconds = Math.floor((Date.now() - chunkStart) / 1000);
    setState((s) => ({ ...s, running: false, chunkStart: null, accumulated: s.accumulated + seconds }));
    await persistChunk(chunkStart, seconds, state.subjectId);
  };

  const reset = async () => {
    if (state.running) await pause();
    setState((s) => ({ ...EMPTY, subjectId: s.subjectId }));
  };

  const setSubject = (subjectId: number | null) => setState((s) => ({ ...s, subjectId }));

  return { elapsed, status, goal, running: state.running, subjectId: state.subjectId, start, pause, reset, setSubject };
}
