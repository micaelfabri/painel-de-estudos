import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

vi.mock("@/lib/sound", () => ({ playGoal: vi.fn(), playAlarm: vi.fn(), unlockAudio: vi.fn() }));
const post = vi.fn();
const patch = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { post: (...a: unknown[]) => post(...a), patch: (...a: unknown[]) => patch(...a) },
}));

import { useStudyTimer } from "@/components/panel/useStudyTimer";

beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
  post.mockImplementation((path: string) => Promise.resolve(path === "/study/timer-sessions" ? { id: 7 } : {}));
  patch.mockImplementation((_path: string, body: Record<string, unknown>) =>
    Promise.resolve({ id: 7, pauses: 2, active_seconds: 120, wall_seconds: 200, end_reason: body.end_reason ?? null }),
  );
});
afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

test("conta as pausas, salva os trechos na sessão e finaliza (D24)", async () => {
  const closed = vi.fn();
  const { result } = renderHook(() => useStudyTimer(90, 120, undefined, closed));
  await act(async () => result.current.start());
  expect(post).toHaveBeenCalledWith("/study/timer-sessions", expect.objectContaining({ subject_id: null }));
  act(() => vi.advanceTimersByTime(60_000));
  await act(async () => result.current.pause());
  expect(result.current.pauses).toBe(1);
  expect(post).toHaveBeenCalledWith("/study-sessions", expect.objectContaining({ seconds: 60, timer_session_id: 7 }));
  expect(patch).toHaveBeenCalledWith("/study/timer-sessions/7", { pauses: 1 });

  act(() => vi.advanceTimersByTime(40_000)); // pausado: não conta
  await act(async () => result.current.start());
  expect(post).toHaveBeenCalledTimes(2); // não abre outra sessão
  act(() => vi.advanceTimersByTime(60_000));
  await act(async () => result.current.finish());
  // Finalizar com o cronômetro rodando salva o trecho, mas não conta como pausa
  expect(patch).toHaveBeenLastCalledWith(
    "/study/timer-sessions/7",
    expect.objectContaining({ end_reason: "finished" }),
  );
  expect(patch).not.toHaveBeenCalledWith("/study/timer-sessions/7", { pauses: 2 });
  expect(closed).toHaveBeenCalledWith(expect.objectContaining({ end_reason: "finished" }));
  expect(result.current.status).toBe("idle");
  expect(result.current.pauses).toBe(0);
});

test("pausa antes do servidor criar a sessão ainda liga o trecho a ela (v1.5)", async () => {
  // A criação da sessão demora; a pausa chega antes da resposta
  let resolveSession: (v: { id: number }) => void = () => {};
  post.mockImplementation((path: string) =>
    path === "/study/timer-sessions"
      ? new Promise((r) => {
          resolveSession = r;
        })
      : Promise.resolve({}),
  );
  const { result } = renderHook(() => useStudyTimer(90, 120));
  act(() => result.current.start());
  act(() => vi.advanceTimersByTime(5_000));
  let paused: Promise<void> = Promise.resolve();
  act(() => {
    paused = result.current.pause();
  });
  await act(async () => {
    resolveSession({ id: 9 });
    await paused;
  });
  expect(post).toHaveBeenCalledWith("/study-sessions", expect.objectContaining({ seconds: 5, timer_session_id: 9 }));
  expect(patch).toHaveBeenCalledWith("/study/timer-sessions/9", { pauses: 1 });
});
