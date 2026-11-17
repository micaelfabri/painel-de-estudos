import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

// v1.10 (D52): prints na conversa por anexo ou Ctrl+V
const sendChat = vi.fn();
vi.mock("@/components/agent/AgentContext", () => ({ useAgent: () => ({ sendChat, pending: null }) }));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { ChatInput } from "@/components/agent/Conversation";

afterEach(() => vi.clearAllMocks());

const png = (name = "print.png") => new File([new Uint8Array([137, 80, 78, 71])], name, { type: "image/png" });

test("colar um print (Ctrl+V) mostra a prévia e manda junto com o texto", async () => {
  render(<ChatInput />);
  const box = screen.getByLabelText("Mensagem para o agente");
  fireEvent.paste(box, { clipboardData: { files: [png()] } });
  expect(await screen.findByAltText("Imagem 1 para enviar")).toBeTruthy();
  fireEvent.change(box, { target: { value: "O que diz?" } });
  fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
  expect(sendChat).toHaveBeenCalledWith("O que diz?", [expect.stringMatching(/^data:image\/png;base64,/)]);
  expect(screen.queryByAltText("Imagem 1 para enviar")).toBeNull();
});

test("anexar: só imagem, até 3, e dá para remover; sem texto manda 'Veja a imagem.'", async () => {
  const { toast } = await import("sonner");
  const { container } = render(<ChatInput />);
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  const pdf = new File(["x"], "a.pdf", { type: "application/pdf" });
  fireEvent.change(input, { target: { files: [png("1.png"), png("2.png"), png("3.png"), png("4.png"), pdf] } });
  await waitFor(() => expect(screen.getAllByRole("img")).toHaveLength(3));
  expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("Só dá para mandar imagens"));
  expect(toast.error).toHaveBeenCalledWith("No máximo 3 imagens por mensagem.");
  expect((screen.getByRole("button", { name: "Anexar imagem" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Remover imagem 2" }));
  expect(screen.getAllByRole("img")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
  expect(sendChat).toHaveBeenCalledWith("Veja a imagem.", expect.arrayContaining([expect.any(String)]));
});
