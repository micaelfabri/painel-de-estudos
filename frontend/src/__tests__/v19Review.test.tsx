import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

// v1.9: Revisão (D51) e questões da disciplina inteira (D50)
const get = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { get: (p: string) => get(p), post: vi.fn(), patch: vi.fn(), put: vi.fn(), del: vi.fn() },
}));
const startSet = vi.fn();
const setPreset = vi.fn();
vi.mock("@/components/agent/AgentContext", () => ({
  useAgent: () => ({
    startSet,
    pending: null,
    generate: vi.fn(),
    topicId: null,
    setTopicId: vi.fn(),
    preset: null,
    setPreset,
  }),
}));

import { GenerateForm } from "@/components/agent/GenerateForm";
import { ReviewPage } from "@/pages/ReviewPage";

afterEach(() => vi.clearAllMocks());
// O Select (Radix) usa APIs que o jsdom não tem
Element.prototype.scrollIntoView = vi.fn();
Element.prototype.hasPointerCapture = vi.fn(() => false);
Element.prototype.releasePointerCapture = vi.fn();

const review = {
  reasons: {
    failed: "Não aprovado",
    not_learned: "Não aprendeu o suficiente",
    not_consolidated: "Aprovado, mas não consolidado",
    not_seen_all: "Aprovado, mas não viu tudo",
  },
  semesters: [
    {
      semester_id: 2,
      code: "2025.2",
      is_current: false,
      counts: { failed: 1, not_learned: 0, not_consolidated: 1, not_seen_all: 0 },
      subjects: [
        {
          id: 9,
          name: "Banco de Dados",
          status: "failed",
          reasons: [{ key: "failed", label: "Não aprovado", detail: "Disciplina reprovada." }],
          topics: [],
          more_topics: 0,
          has_text: false,
        },
        {
          id: 5,
          name: "Segurança de Software",
          status: "passed",
          reasons: [
            { key: "not_consolidated", label: "Aprovado, mas não consolidado", detail: "2 erro(s) não corrigido(s)." },
          ],
          topics: [{ id: 28, title: "Princípios", why: ["2 erro(s) não corrigido(s)"], has_text: true }],
          more_topics: 0,
          has_text: true,
        },
      ],
    },
  ],
};

test("Revisão: semestre com as disciplinas, motivos e questões da disciplina", async () => {
  get.mockImplementation((p: string) =>
    Promise.resolve(
      p.startsWith("/review") ? review : p === "/settings" ? { values: { options_per_question: 4 }, schema: [] } : [],
    ),
  );
  render(
    <MemoryRouter>
      <ReviewPage />
    </MemoryRouter>,
  );
  expect(await screen.findByRole("heading", { name: /Semestre 2025\.2\s*· em revisão/ })).toBeTruthy();
  expect(screen.getByText(/2 disciplina\(s\) · 1 não aprovado · 1 aprovado, mas não consolidado/)).toBeTruthy();
  expect(screen.getByText("Disciplina reprovada.")).toBeTruthy();
  // Sem texto salvo: botão desligado com o motivo
  const buttons = screen.getAllByRole("button", { name: "Questões da disciplina" });
  expect((buttons[0] as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText(/Nenhum tema com texto salvo nem página do Notion/)).toBeTruthy();
  fireEvent.click(buttons[1]);
  expect(startSet).toHaveBeenCalledWith(
    expect.objectContaining({ path: "/agent/question-sets/subject", body: { subject_id: 5, n_options: 4 } }),
  );
});

test("Revisão vazia explica quando aparece algo", async () => {
  get.mockImplementation((p: string) => Promise.resolve(p.startsWith("/review") ? { ...review, semesters: [] } : []));
  render(
    <MemoryRouter>
      <ReviewPage />
    </MemoryRouter>,
  );
  expect(await screen.findByText(/Nada em revisão/)).toBeTruthy();
});

test("Gerar questões: a disciplina inteira vai para o endpoint da disciplina", async () => {
  get.mockImplementation((p: string) =>
    Promise.resolve(
      p === "/overview"
        ? { subjects: [{ id: 5, name: "Segurança de Software" }] }
        : p === "/settings"
          ? { values: { options_per_question: 5 }, schema: [] }
          : p.startsWith("/topics?")
            ? [
                { id: 28, title: "Princípios", portal_done: true, source_text: "texto", notion_page_id: null },
                { id: 29, title: "Questões", portal_done: false, source_text: null, notion_page_id: null },
              ]
            : [],
    ),
  );
  const onDone = vi.fn();
  render(<GenerateForm onDone={onDone} />);
  // escolhe a disciplina e depois "Disciplina inteira"
  fireEvent.click(await screen.findByRole("combobox", { name: "Disciplina" }));
  fireEvent.click(await screen.findByRole("option", { name: "Segurança de Software" }));
  await waitFor(() => expect(get).toHaveBeenCalledWith("/topics?subject_id=5"));
  fireEvent.click(screen.getByRole("combobox", { name: "Tema" }));
  fireEvent.click(await screen.findByRole("option", { name: "Disciplina inteira (1 tema(s) com texto ou Notion)" }));
  expect(screen.queryByLabelText(/Texto do tema/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Gerar questões da disciplina" }));
  expect(startSet).toHaveBeenCalledWith(
    expect.objectContaining({ path: "/agent/question-sets/subject", body: { subject_id: 5, n_options: 5 } }),
  );
  expect(onDone).toHaveBeenCalled();
});
