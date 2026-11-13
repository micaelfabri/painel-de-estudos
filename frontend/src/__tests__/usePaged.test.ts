import { act, renderHook } from "@testing-library/react";
import { expect, test } from "vitest";

import { usePaged } from "@/lib/usePaged";

const rows = (n: number) => Array.from({ length: n }, (_, i) => i + 1);

// v1.7.2: 10 por página, volta para a 1 ao trocar o filtro, não passa da última quando a lista encolhe
test("pages of 10, reset on filter change, clamp when the list shrinks", () => {
  const { result, rerender } = renderHook(({ list, key }) => usePaged(list, key), {
    initialProps: { list: rows(23), key: "all" },
  });
  expect(result.current.pages).toBe(3);
  expect(result.current.slice).toEqual(rows(10));
  act(() => result.current.goTo(3));
  expect(result.current.slice).toEqual([21, 22, 23]);

  rerender({ list: rows(12), key: "all" });
  expect(result.current.page).toBe(2);
  expect(result.current.slice).toEqual([11, 12]);

  rerender({ list: rows(12), key: "subject-1" });
  expect(result.current.page).toBe(1);
});
