import { render, screen } from "@testing-library/react";

import { InlineMeter } from "@/components/panel/InlineMeter";

describe("InlineMeter (DS v2.13)", () => {
  it("abaixo do limiar: neutro, sem 'Aprendido'", () => {
    render(<InlineMeter label="Tema 3" value={60} threshold={70} />);
    const meter = screen.getByRole("meter");
    expect(meter.getAttribute("aria-valuetext")).toBe("60%, abaixo de 70% para aprendido");
    expect(screen.queryByText("Aprendido")).toBeNull();
  });

  it("no limiar: mostra ícone e texto 'Aprendido'", () => {
    render(<InlineMeter label="Tema 1" value={80} threshold={70} />);
    expect(screen.getByText("Aprendido")).toBeTruthy();
  });
});
