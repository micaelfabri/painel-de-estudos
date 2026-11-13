import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { CardView } from "@/lib/api";

const post = vi.fn();
vi.mock("@/lib/api", () => ({ api: { post: (...a: unknown[]) => post(...a) } }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }));

import { CardReview } from "@/components/cards/CardReview";

afterEach(() => vi.clearAllMocks());

const tomorrow = () => {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const card: CardView = {
  id: 3,
  topic_id: 1,
  topic_title: "Tema 4",
  subject_id: 5,
  subject_name: "Segurança de Software",
  kind: "question",
  kind_label: "Questão virada card",
  mode: "answer",
  front: "Qual é a defesa principal contra injeção de SQL?",
  back: "Consultas parametrizadas.",
  explanation: "O dado vai separado do comando.",
  options: ["Escapar aspas", "Consultas parametrizadas", "Variável de ambiente", "HTTPS"],
  correct_index: 1,
  source: "mistake",
  source_label: "Do erro",
  source_detail: null,
  mistake_id: 9,
  mistake_status: "again",
  chosen_text: "Escapar aspas",
  video_minute: "12:40",
  notion_url: null,
  step: 0,
  next_review: "2026-11-12",
  due: true,
};

test("Responder errado: marca sua resposta e a correta e diz que o erro volta para revisar (D33)", async () => {
  post.mockResolvedValue({ knew: false, correct_index: 1, card: { ...card, next_review: tomorrow() } });
  const onNext = vi.fn();
  render(<CardReview card={card} position="Card 3 de 10" onNext={onNext} />);
  expect(screen.getByText("Do erro: revisar de novo").className).toContain("rounded-full");
  fireEvent.click(screen.getByRole("radio", { name: /Escapar aspas/ }));
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Responder" }));
  });
  expect(post).toHaveBeenCalledWith("/cards/3/review", { mode: "answer", chosen_index: 0 });
  expect(screen.getByText('Este erro volta para "revisar de novo" e o card volta amanhã.')).toBeTruthy();
  expect(screen.getByText("Sua resposta")).toBeTruthy();
  expect(screen.getByText("Correta")).toBeTruthy();
  expect(screen.getByText(/vídeo 12:40/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Próximo card" }));
  expect(onNext).toHaveBeenCalled();
});

test("Virar: mostra o verso e manda Sabia", async () => {
  post.mockResolvedValue({
    knew: true,
    correct_index: 1,
    card: { ...card, mistake_status: "reviewed", next_review: tomorrow() },
  });
  render(<CardReview card={{ ...card, mode: "flip" }} />);
  expect(screen.queryByText("Consultas parametrizadas.")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Virar card" }));
  expect(screen.getByText("Consultas parametrizadas.")).toBeTruthy();
  expect(screen.getByText('Quando errou, você marcou "Escapar aspas".')).toBeTruthy();
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Sabia" }));
  });
  expect(post).toHaveBeenCalledWith("/cards/3/review", { mode: "flip", knew: true });
  expect(screen.getByText("Marcado como sabia. O card volta amanhã.")).toBeTruthy();
});
