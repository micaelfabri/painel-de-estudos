import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

vi.mock("@/lib/sound", () => ({ playGoal: vi.fn(), playAlarm: vi.fn(), unlockAudio: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: { post: vi.fn().mockResolvedValue({}) } }));

import { playAlarm, playGoal, unlockAudio } from "@/lib/sound";
import { useStudyTimer } from "@/components/panel/useStudyTimer";

beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
});
afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

test("toca na meta e no alarme, uma vez cada", () => {
  // meta 1 min, alarme 2 min
  const { result } = renderHook(() => useStudyTimer(1, 2));
  act(() => result.current.start());
  expect(unlockAudio).toHaveBeenCalled();
  act(() => vi.advanceTimersByTime(61_000));
  expect(playGoal).toHaveBeenCalledTimes(1);
  expect(playAlarm).not.toHaveBeenCalled();
  act(() => vi.advanceTimersByTime(60_000));
  expect(playAlarm).toHaveBeenCalledTimes(1);
  act(() => vi.advanceTimersByTime(30_000));
  expect(playGoal).toHaveBeenCalledTimes(1);
  expect(playAlarm).toHaveBeenCalledTimes(1);
});
