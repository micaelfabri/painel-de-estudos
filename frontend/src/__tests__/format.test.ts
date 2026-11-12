import { daysBetween, formatClock, formatDuration, parseLocalDate, relativeDays } from "@/lib/format";

describe("formatação pt-BR", () => {
  it("formata duração e relógio", () => {
    expect(formatDuration(5400)).toBe("1h30");
    expect(formatDuration(600)).toBe("10 min");
    expect(formatDuration(7200)).toBe("2h");
    expect(formatClock(4320)).toBe("01:12:00");
    expect(formatClock(75)).toBe("01:15");
  });

  it("conta dias sem deslocar pelo fuso", () => {
    expect(daysBetween(parseLocalDate("2026-11-10"), parseLocalDate("2026-11-17"))).toBe(7);
    expect(relativeDays(0)).toBe("hoje");
    expect(relativeDays(3)).toBe("em 3 dias");
  });
});
