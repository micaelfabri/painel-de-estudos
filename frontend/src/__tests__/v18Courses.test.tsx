import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

// v1.8 (D38–D44): telas de Cursos e certificados com api e agente falsos
const get = vi.fn();
const post = vi.fn();
const patch = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    get: (p: string) => get(p),
    post: (...a: unknown[]) => post(...a),
    patch: (...a: unknown[]) => patch(...a),
    put: vi.fn(),
    del: vi.fn(),
  },
  agentErrorMessage: () => "erro",
}));
const startSet = vi.fn();
vi.mock("@/components/agent/AgentContext", () => ({
  useAgent: () => ({ startSet, pending: null, learningVersion: 0, openCards: vi.fn(), model: "m" }),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));
// O cronômetro tem testes próprios; aqui só importa a página
vi.mock("@/components/panel/TimerCard", () => ({ TimerCard: () => <div>cronômetro</div> }));

import { CourseDetailPage } from "@/pages/CourseDetailPage";
import { CoursesPage } from "@/pages/CoursesPage";

afterEach(() => vi.clearAllMocks());

const course = (over: Record<string, unknown> = {}) => ({
  id: 7,
  name: "AWS Cloud Practitioner",
  platform: "Alura",
  course_type: "certification",
  type_label: "Certificação com prova",
  course_status: "doing",
  status_label: "Fazendo",
  url: "https://alura.com.br/curso",
  total_hours: 20,
  start_date: "2026-11-01",
  target_date: null,
  days_to_target: null,
  exam_at: "2026-12-10T09:00",
  days_to_exam: 27,
  certificate_path: null,
  counts_acc: true,
  acc_category: "Cursos",
  acc_activity_id: null,
  notion_page_id: null,
  notion_url: null,
  manual_progress: null,
  finished_on: null,
  notes: null,
  progress: 50,
  modules_total: 2,
  modules_done: 1,
  seconds: 3600,
  week_seconds: 1800,
  sets: 1,
  cards: 4,
  average_score: 0.8,
  next_lesson: { module: "Módulo 2", title: "IAM" },
  modules: [
    { id: 11, number: 1, name: "Conceitos", status: "passed", lessons: [] },
    {
      id: 12,
      number: 2,
      name: "Segurança",
      status: "in_progress",
      lessons: [
        { id: 21, title: "IAM", done: false, has_text: true, last_score: null },
        { id: 22, title: "KMS", done: false, has_text: false, last_score: null },
      ],
    },
  ],
  ...over,
});

test("Meus cursos: KPIs, abas por situação e card com link externo seguro (K1)", async () => {
  get.mockImplementation((path: string) =>
    Promise.resolve(
      path === "/courses/summary"
        ? {
            week_seconds: 1800,
            goal_hours: 5,
            certificates: 2,
            acc_hours: 40,
            counts: { doing: 1, wishlist: 3, paused: 0, done: 2 },
            next_exam: { name: "AWS Cloud Practitioner", exam_at: "2026-12-10T09:00", days: 27 },
          }
        : [course()],
    ),
  );
  render(
    <MemoryRouter initialEntries={["/cursos"]}>
      <CoursesPage />
    </MemoryRouter>,
  );
  expect(await screen.findByRole("link", { name: "AWS Cloud Practitioner" })).toBeTruthy();
  expect(screen.getByText("esta semana · meta 5h")).toBeTruthy();
  expect(screen.getByRole("tab", { name: "Fazendo (1)" }).getAttribute("aria-selected")).toBe("true");
  const ext = screen.getByRole("link", { name: /Abrir no Alura/ });
  expect(ext.getAttribute("rel")).toBe("noopener noreferrer");

  // Setas trocam de aba e pedem a lista daquela situação
  fireEvent.keyDown(screen.getByRole("tab", { name: "Fazendo (1)" }), { key: "ArrowRight" });
  await waitFor(() => expect(get).toHaveBeenCalledWith("/courses?status=wishlist"));
});

test("Página do curso: aula marcada, questões só com texto e AAC só ao concluir (K2, K3)", async () => {
  get.mockImplementation((path: string) =>
    Promise.resolve(path === "/settings" ? { values: { options_per_question: 4 }, schema: [] } : course()),
  );
  patch.mockResolvedValue({});
  render(
    <MemoryRouter initialEntries={["/cursos/7"]}>
      <Routes>
        <Route path="/cursos/:id" element={<CourseDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
  expect(await screen.findByRole("heading", { level: 1, name: "AWS Cloud Practitioner" })).toBeTruthy();
  expect(screen.getByRole("link", { name: "Meus cursos" })).toBeTruthy();

  fireEvent.click(screen.getByRole("checkbox", { name: /IAM/ }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith("/courses/lessons/21", { done: true }));

  // KMS não tem texto: sem questões; IAM tem: gera com o número de opções das configurações
  expect((screen.getByRole("button", { name: /Questões\s*de KMS/ }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: /Questões\s*de IAM/ }));
  expect(startSet).toHaveBeenCalledWith(
    expect.objectContaining({ path: "/agent/question-sets", body: { topic_id: 21, n_options: 4 } }),
  );

  // Curso em andamento: o botão da AAC existe mas fica desligado
  expect((screen.getByRole("button", { name: "Lançar como AAC" }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText("Prova de certificação")).toBeTruthy();
});

test("Página do curso concluído: lança a AAC uma vez (K3)", async () => {
  const done = course({ course_status: "done", status_label: "Concluído", finished_on: "2026-11-12" });
  get.mockImplementation((path: string) => Promise.resolve(path === "/settings" ? { values: {}, schema: [] } : done));
  post.mockResolvedValue({ title: "Alura - AWS Cloud Practitioner", hours: 20 });
  render(
    <MemoryRouter initialEntries={["/cursos/7"]}>
      <Routes>
        <Route path="/cursos/:id" element={<CourseDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
  const btn = await screen.findByRole("button", { name: "Lançar como AAC" });
  expect((btn as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(btn);
  await waitFor(() => expect(post).toHaveBeenCalledWith("/courses/7/acc", {}));
});
