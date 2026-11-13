import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { Pagination } from "@/components/ui/pagination";

// v1.7.2: botões de primeira e última página
test("first and last buttons jump to the ends and are disabled at the ends", () => {
  const onPage = vi.fn();
  const { rerender } = render(<Pagination page={2} pages={4} total={38} onPage={onPage} />);
  fireEvent.click(screen.getByRole("button", { name: "Última página" }));
  expect(onPage).toHaveBeenLastCalledWith(4);
  fireEvent.click(screen.getByRole("button", { name: "Primeira página" }));
  expect(onPage).toHaveBeenLastCalledWith(1);

  rerender(<Pagination page={1} pages={4} onPage={onPage} />);
  expect((screen.getByRole("button", { name: "Primeira página" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Anterior" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "Última página" }) as HTMLButtonElement).disabled).toBe(false);

  rerender(<Pagination page={4} pages={4} onPage={onPage} />);
  expect((screen.getByRole("button", { name: "Última página" }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: /Próxima/ }) as HTMLButtonElement).disabled).toBe(true);
});
