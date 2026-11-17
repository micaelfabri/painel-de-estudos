import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

// v1.8.2: perguntar se marca os temas ao concluir a tarefa; apagar tema na edição de temas
const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
const del = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    get: (p: string) => get(p),
    post: (...a: unknown[]) => post(...a),
    patch: (...a: unknown[]) => patch(...a),
    put: vi.fn(),
    del: (p: string) => del(p),
  },
}));
vi.mock("@/components/agent/AgentContext", () => ({
  useAgent: () => ({ setPreset: vi.fn(), learningVersion: 0 }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

import { DailyChecklist } from "@/components/agent/DailyChecklist";
import { TopicsDialog } from "@/components/manage/TopicsDialog";
import type { Subject } from "@/lib/api";

afterEach(() => vi.clearAllMocks());

const task = {
  id: 9,
  day: "2026-11-15",
  label: "Concluir Tema 3 e Tema 4 · Engenharia de Requisitos",
  planned_minutes: 90,
  topic_id: 3,
  review_id: null,
  done: false,
  position: 1,
};

test("concluir a tarefa de tema pergunta se marca os temas no portal", async () => {
  get.mockImplementation((path: string) =>
    Promise.resolve(
      path.startsWith("/learning/checklist?")
        ? [task]
        : path === "/learning/checklist/9/topics"
          ? [
              { id: 3, title: "Tema 3", portal_done: false },
              { id: 4, title: "Tema 4", portal_done: false },
            ]
          : [],
    ),
  );
  patch.mockResolvedValue({});
  post.mockResolvedValue({ marked: ["Tema 3", "Tema 4"] });
  render(
    <MemoryRouter>
      <DailyChecklist />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("checkbox", { name: /Concluir Tema 3 e Tema 4/ }));
  expect(await screen.findByRole("heading", { name: "Marcar os temas como concluídos?" })).toBeTruthy();
  expect(screen.getByText(/Tema 3, Tema 4 passa/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Marcar como concluídos" }));
  await waitFor(() => expect(post).toHaveBeenCalledWith("/learning/checklist/9/topics-done", {}));
  // O link para as tarefas dos outros dias leva ao Histórico
  expect(screen.getByRole("link", { name: "Ver as tarefas dos outros dias" }).getAttribute("href")).toBe(
    "/estudo/historico#tarefas",
  );
});

test("tarefa cujos temas já estão concluídos não pergunta nada", async () => {
  get.mockImplementation((path: string) =>
    Promise.resolve(
      path.startsWith("/learning/checklist?")
        ? [task]
        : path === "/learning/checklist/9/topics"
          ? [{ id: 3, title: "Tema 3", portal_done: true }]
          : [],
    ),
  );
  patch.mockResolvedValue({});
  render(
    <MemoryRouter>
      <DailyChecklist />
    </MemoryRouter>,
  );
  fireEvent.click(await screen.findByRole("checkbox", { name: /Concluir Tema 3 e Tema 4/ }));
  await waitFor(() => expect(get).toHaveBeenCalledWith("/learning/checklist/9/topics"));
  expect(screen.queryByRole("heading", { name: "Marcar os temas como concluídos?" })).toBeNull();
});

const subject = { id: 1, name: "Engenharia de Requisitos" } as Subject;
const topic = (id: number, title: string) => ({
  id,
  subject_id: 1,
  title,
  position: id,
  portal_done: false,
  notion_page_id: null,
  source_text: null,
});

test("apagar tema: confirma e chama o servidor; o recusado mostra o motivo e fica", async () => {
  get.mockImplementation((path: string) =>
    Promise.resolve(path.startsWith("/topics?") ? [topic(7, "Tema 7"), topic(8, "Tema 8")] : []),
  );
  del.mockImplementation((path: string) =>
    path === "/topics/7"
      ? Promise.reject(new Error("Tema 7 tem histórico (1 tarefa(s)) e não pode ser apagado."))
      : Promise.resolve(undefined),
  );
  const onSaved = vi.fn();
  render(<TopicsDialog subject={subject} onOpenChange={() => {}} onSaved={onSaved} />);

  // O título fica num campo próprio, com o rótulo acessível
  expect((await screen.findByLabelText("Título do tema 2")) as HTMLInputElement).toHaveProperty("value", "Tema 8");

  fireEvent.click(screen.getByRole("button", { name: "Apagar Tema 8" }));
  fireEvent.click(await screen.findByRole("button", { name: "Apagar tema" }));
  await waitFor(() => expect(del).toHaveBeenCalledWith("/topics/8"));
  await waitFor(() => expect(screen.queryByDisplayValue("Tema 8")).toBeNull());
  expect(onSaved).toHaveBeenCalled();

  const { toast } = await import("sonner");
  fireEvent.click(screen.getByRole("button", { name: "Apagar Tema 7" }));
  fireEvent.click(await screen.findByRole("button", { name: "Apagar tema" }));
  await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("tem histórico")));
  expect(screen.getByDisplayValue("Tema 7")).toBeTruthy();
});

test("tema novo, ainda não salvo, sai da lista sem chamar o servidor", async () => {
  get.mockImplementation((path: string) => Promise.resolve(path.startsWith("/topics?") ? [topic(7, "Tema 7")] : []));
  render(<TopicsDialog subject={subject} onOpenChange={() => {}} onSaved={() => {}} />);
  await screen.findByDisplayValue("Tema 7");
  fireEvent.click(screen.getByRole("button", { name: "Adicionar tema" }));
  fireEvent.click(await screen.findByRole("button", { name: "Apagar Tema 2" }));
  expect(screen.queryByDisplayValue("Tema 2")).toBeNull();
  expect(del).not.toHaveBeenCalled();
});
