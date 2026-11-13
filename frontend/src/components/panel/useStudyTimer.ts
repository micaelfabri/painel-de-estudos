import * as React from "react";

import { api, type TimerSessionView } from "@/lib/api";
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
  /** v1.4 (D24): sessão no servidor, início do relógio oculto e quantas pausas */
  timerId?: number | null;
  sessionStart?: number | null;
  pauses?: number;
}

const EMPTY: StoredTimer = {
  subjectId: null,
  running: false,
  accumulated: 0,
  chunkStart: null,
  timerId: null,
  sessionStart: null,
  pauses: 0,
};

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
 * Cronômetro de estudo. Cada trecho entre Iniciar e Pausar vira um trecho salvo na API
 * (SPEC §6.1). Desde a v1.4 (D24) os trechos ficam dentro de uma sessão do cronômetro,
 * que conta as pausas e um relógio "oculto" do primeiro Iniciar até Finalizar. Desde a v1.7.2, Cancelar
 * descarta a sessão e os trechos (o antigo Zerar salvava o tempo, e um Iniciar por engano virava sessão de 0 min).
 */
const ALARM_REPEAT = 10 * 60; // segundos entre repetições do alarme

export function useStudyTimer(
  goalMinutes: number,
  alarmMinutes: number,
  onSaved?: (seconds: number) => void,
  onClosed?: (session: TimerSessionView) => void,
  onCancelled?: () => void,
) {
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
      const due =
        prev !== "alarm" ? prev === "past_goal" || prev === "running" : elapsed - lastAlarmAt.current >= ALARM_REPEAT;
      if (due) {
        lastAlarmAt.current = elapsed;
        playAlarm();
      }
    }
  }, [status, elapsed]);

  const persistChunk = React.useCallback(
    async (start: number, seconds: number, subjectId: number | null, timerId: number | null) => {
      if (seconds < 1) return;
      await api.post("/study-sessions", {
        subject_id: subjectId,
        started_at: toIsoLocal(new Date(start)),
        ended_at: toIsoLocal(new Date(start + seconds * 1000)),
        seconds,
        timer_session_id: timerId,
      });
      onSaved?.(seconds);
    },
    [onSaved],
  );

  // v1.5: a sessão do servidor pode ainda estar sendo criada quando chega a primeira pausa;
  // os trechos esperam por esta promessa para não ficarem sem sessão
  const opening = React.useRef<Promise<number | null> | null>(null);
  const timerIdNow = async (): Promise<number | null> =>
    state.timerId ?? (opening.current ? await opening.current : null);

  const start = () => {
    unlockAudio();
    const at = Date.now();
    setNow(at);
    setState((s) => ({ ...s, running: true, chunkStart: at, sessionStart: s.sessionStart ?? at }));
    if (state.timerId == null && opening.current == null) {
      // Primeiro Iniciar: abre a sessão no servidor sem atrasar o cronômetro (se falhar, seguem só os trechos)
      opening.current = api
        .post<TimerSessionView>("/study/timer-sessions", {
          subject_id: state.subjectId,
          started_at: toIsoLocal(new Date(at)),
        })
        .then((t) => {
          setState((s) => ({ ...s, timerId: s.timerId ?? t.id }));
          return t.id;
        })
        .catch(() => null);
    }
  };

  /** Fecha o trecho atual; `countPause` = foi o botão Pausar (Finalizar não conta como pausa) */
  const stopChunk = async (countPause: boolean) => {
    const chunkStart = state.chunkStart ?? Date.now();
    const seconds = Math.floor((Date.now() - chunkStart) / 1000);
    const pauses = (state.pauses ?? 0) + (countPause ? 1 : 0);
    setState((s) => ({ ...s, running: false, chunkStart: null, accumulated: s.accumulated + seconds, pauses }));
    const timerId = await timerIdNow();
    await persistChunk(chunkStart, seconds, state.subjectId, timerId);
    if (countPause && timerId) await api.patch(`/study/timer-sessions/${timerId}`, { pauses });
  };

  const pause = () => stopChunk(true);

  const close = async (reason: "finished") => {
    if (state.running) await stopChunk(false);
    const timerId = await timerIdNow();
    opening.current = null;
    setState((s) => ({ ...EMPTY, subjectId: s.subjectId }));
    if (timerId) {
      const t = await api.patch<TimerSessionView>(`/study/timer-sessions/${timerId}`, {
        end_reason: reason,
        ended_at: toIsoLocal(new Date()),
      });
      onClosed?.(t);
    }
  };

  const finish = () => close("finished");

  /** v1.7.2: descarta a sessão (o trecho em andamento não é salvo; os já salvos são apagados no servidor) */
  const cancel = async () => {
    const timerId = await timerIdNow();
    opening.current = null;
    setState((s) => ({ ...EMPTY, subjectId: s.subjectId }));
    if (timerId) await api.del(`/study/timer-sessions/${timerId}`);
    onCancelled?.();
  };

  const setSubject = (subjectId: number | null) => {
    setState((s) => ({ ...s, subjectId }));
    if (state.timerId)
      void api.patch(`/study/timer-sessions/${state.timerId}`, { subject_id: subjectId }).catch(() => {});
  };

  return {
    elapsed,
    status,
    goal,
    running: state.running,
    subjectId: state.subjectId,
    pauses: state.pauses ?? 0,
    start,
    pause,
    finish,
    cancel,
    setSubject,
  };
}
