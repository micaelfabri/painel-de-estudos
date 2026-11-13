// Formatação em pt-BR (DS: Intl, nunca formatação manual)
const LOCALE = "pt-BR";

export function parseLocalDate(iso: string): Date {
  // "2026-11-17" vira data local (sem deslocar o dia pelo fuso)
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function parseLocalDateTime(iso: string): Date {
  // A API devolve data e hora locais sem fuso ("2026-11-17T17:00:00")
  const [date, time = "00:00:00"] = iso.split("T");
  const [y, m, d] = date.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  return new Date(y, m - 1, d, hh, mm);
}

export const formatDayMonth = (d: Date) => new Intl.DateTimeFormat(LOCALE, { day: "2-digit", month: "2-digit" }).format(d);

export const formatTime = (d: Date) => new Intl.DateTimeFormat(LOCALE, { hour: "2-digit", minute: "2-digit" }).format(d);

export const formatWeekdayShort = (d: Date) => new Intl.DateTimeFormat(LOCALE, { weekday: "short" }).format(d).replace(".", "");

export const formatWeekdayLong = (d: Date) => {
  const w = new Intl.DateTimeFormat(LOCALE, { weekday: "long" }).format(d);
  return w.charAt(0).toUpperCase() + w.slice(1);
};

export const formatLongDate = (d: Date) =>
  new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "numeric", month: "long" }).format(d);

export const formatFullDate = (d: Date) =>
  new Intl.DateTimeFormat(LOCALE, { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" }).format(d);

export const formatNumber = (n: number, digits = 0) => new Intl.NumberFormat(LOCALE, { maximumFractionDigits: digits }).format(n);

/** 5400 s -> "1h30"; 600 s -> "10 min" */
export function formatDuration(seconds: number): string {
  const total = Math.round(seconds / 60);
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h}h` : `${h}h${String(m).padStart(2, "0")}`;
}

/** Relógio do cronômetro: 4320 s -> "01:12:00"; abaixo de 1h -> "12:00" */
export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(sec).padStart(2, "0");
  return h > 0 ? `${String(h).padStart(2, "0")}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function daysBetween(from: Date, to: Date): number {
  const a = new Date(from.getFullYear(), from.getMonth(), from.getDate()).getTime();
  const b = new Date(to.getFullYear(), to.getMonth(), to.getDate()).getTime();
  return Math.round((b - a) / 86_400_000);
}

/** "em 3 dias", "amanhã", "hoje" */
export function relativeDays(days: number): string {
  if (days === 0) return "hoje";
  if (days === 1) return "amanhã";
  if (days < 0) return days === -1 ? "ontem" : `há ${-days} dias`;
  return `em ${days} dias`;
}

export function toIsoLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
