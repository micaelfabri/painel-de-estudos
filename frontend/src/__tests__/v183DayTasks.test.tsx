import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { DayTaskList } from "@/components/panel/DayTaskList";

// v1.8.3 (D49): a tarefa passada para outro dia aparece como rastro, não como "não feita"
test("rastro de tarefa passada para outro dia e 'começou em' no dia em que foi feita", () => {
  render(
    <DayTaskList
      tasks={[
        { id: 1, label: "Concluir Tema 4 e Tema 5", done: false, planned_minutes: 90, carried_to: "2026-11-16" },
        { id: 2, label: "Concluir Tema 4 e Tema 5 ", done: true, planned_minutes: 90, started_on: "2026-11-15" },
        { id: 3, label: "Ler o capítulo 2", done: false, planned_minutes: null },
      ]}
    />,
  );
  expect(screen.getByText("passou para 16/11")).toBeTruthy();
  expect(screen.getByText("feita · começou em 15/11")).toBeTruthy();
  expect(screen.getByText("não feita")).toBeTruthy();
});
