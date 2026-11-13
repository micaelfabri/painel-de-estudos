import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { HoursChart, ScoresChart } from "@/components/performance/Charts";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

// --- Revisar erros: precisa do api e do agente falsos -------------------------------
const get = vi.fn();
const patch = vi.fn();
vi.mock("@/lib/api", () => ({ api: { get: (p: string) => get(p), patch: (...a: unknown[]) => patch(...a) } }));
const startSet = vi.fn();
vi.mock("@/components/agent/AgentContext", () => ({
  useAgent: () => ({ startSet, pending: null, learningVersion: 0 }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { ReviewMistakes } from "@/components/agent/ReviewMistakes";

afterEach(() => vi.clearAllMocks());

const mistake = (over: Record<string, unknown>) => ({
  id: 1,
  topic_id: 1,
  topic_title: "Tema 4",
  subject_name: "Segurança de Software",
  subject_id: 5,
  statement: "Qual?",
  options: ["a", "b"],
  correct_index: 0,
  chosen_index: 1,
  explanation: null,
  video_minute: null,
  reviewed: false,
  status: "open",
  status_label: "não revisado",
  ...over,
});

test("Revisar erros: status com badge de status, não respondida e refazer (D28)", async () => {
  get.mockImplementation((path: string) =>
    Promise.resolve(
      path.startsWith("/learning/mistakes/summary")
        ? { open: 1, reviewed: 0, again: 1, fixed: 3 }
        : [mistake({}), mistake({ id: 2, status: "again", chosen_index: -1 })],
    ),
  );
  patch.mockResolvedValue({});
  render(<ReviewMistakes onClose={() => {}} />);
  expect(await screen.findByText("1 não revisado · 1 para revisar de novo · 3 corrigidos")).toBeTruthy();
  const badge = screen.getByText("Não revisado");
  expect(badge.className).toContain("rounded-full");
  expect(screen.getByText(/não respondida/)).toBeTruthy();

  fireEvent.click(screen.getAllByRole("button", { name: "Já revisei" })[0]);
  await waitFor(() => expect(patch).toHaveBeenCalledWith("/learning/mistakes/1", { status: "reviewed" }));

  fireEvent.click(screen.getByRole("button", { name: /Refazer erros não corrigidos \(2\)/ }));
  expect(startSet).toHaveBeenCalledWith(expect.objectContaining({ path: "/agent/mistakes/redo" }));
});

// --- Gráficos -------------------------------------------------------------------------
const daily = [
  { date: "2026-11-10", seconds: 9000, sets: 2, cards: 4, average_score: 0.8 },
  { date: "2026-11-11", seconds: 0, sets: 0, cards: 0, average_score: null },
];

test("gráfico de horas: leitura completa no botão, leitura ao focar e clique no dia", () => {
  const onSelect = vi.fn();
  render(<HoursChart daily={daily} selected={null} onSelect={onSelect} />);
  const bar = screen.getByRole("button", { name: /^Terça-feira, 10\/11: 2h30 de estudo, 2 teste\(s\)/ });
  fireEvent.focus(bar);
  expect(screen.getByText("2h30")).toBeTruthy();
  fireEvent.click(bar);
  expect(onSelect).toHaveBeenCalledWith("2026-11-10");
});

test("gráfico de notas: rótulo do limiar, leitura e abrir o teste", () => {
  const onOpen = vi.fn();
  const scores = [
    {
      set_id: 7,
      date: "2026-11-12T10:44:00",
      score: 0.75,
      label: "primeira vez",
      attempt_type: "first",
      topic: "Tema 3",
      subject: "Web",
    },
  ];
  render(<ScoresChart scores={scores} threshold={0.7} onOpen={onOpen} />);
  expect(screen.getByText("70%")).toBeTruthy();
  const point = screen.getByRole("button", { name: "Tema 3 (primeira vez), 12/11: nota 75%. Abrir o teste." });
  fireEvent.click(point);
  expect(onOpen).toHaveBeenCalledWith(7);
});

// --- Confirmação ----------------------------------------------------------------------
test("confirmação: foco no Cancelar, Esc cancela, erro mantém aberto com 'Nada foi alterado.'", async () => {
  const onOpenChange = vi.fn();
  const onConfirm = vi.fn().mockRejectedValueOnce(new Error("Sem conexão"));
  render(
    <ConfirmDialog
      open
      onOpenChange={onOpenChange}
      title="Marcar como feito?"
      note="Vai para Feitos."
      confirmLabel="Marcar como feito"
      onConfirm={onConfirm}
    />,
  );
  const dialog = screen.getByRole("alertdialog");
  expect(dialog.getAttribute("aria-describedby")).toBe(screen.getByRole("note").id);
  await waitFor(() => expect(document.activeElement?.textContent).toBe("Cancelar"));

  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Marcar como feito" }));
  });
  expect(screen.getByRole("alert").textContent).toContain("Nada foi alterado.");
  expect(onOpenChange).not.toHaveBeenCalledWith(false);

  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(onOpenChange).toHaveBeenCalledWith(false);
});

test("gráfico de horas no toque: barras só visuais e Select 'Dia' com os mesmos dias (resposta 04 do DS)", () => {
  const onSelect = vi.fn();
  render(<HoursChart daily={daily} selected={null} onSelect={onSelect} coarse />);
  expect(screen.queryByRole("button", { name: /de estudo/ })).toBeNull();
  expect(screen.queryByRole("list", { name: "Horas por dia" })).toBeNull();
  const select = screen.getByRole("combobox", { name: "Dia" });
  expect(select).toBeTruthy();
  expect(screen.getByText("Escolha um dia abaixo do gráfico")).toBeTruthy();
});
