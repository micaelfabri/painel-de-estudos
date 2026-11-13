import * as React from "react";

import { focusRing } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import type { Metrics } from "@/lib/api";
import {
  formatDayMonth,
  formatDuration,
  formatTime,
  formatWeekdayLong,
  formatWeekdayShort,
  parseLocalDate,
  parseLocalDateTime,
} from "@/lib/format";
import { cn } from "@/lib/utils";

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v * 100)}%`);

/**
 * Leitura do item sob o mouse ou com foco (v1.5): fica acima do gráfico, sem cobrir as marcas.
 * Valor em destaque, rótulo depois. Tudo o que aparece aqui também está na tabela escondida.
 */
function Readout({ value, label, hint }: { value: string; label: string; hint: string }) {
  return (
    <p aria-live="polite" className="min-h-10 text-sm">
      <span className="font-semibold tabular-nums">{value}</span> <span className="text-muted-foreground">{label}</span>
      <span className="block text-xs text-muted-foreground">{hint}</span>
    </p>
  );
}

/** Leitura completa de um dia (botão da barra e opção do Select "Dia") */
function dayReading(d: Metrics["daily"][number]) {
  const day = parseLocalDate(d.date);
  return `${formatWeekdayLong(day)}, ${formatDayMonth(day)}: ${formatDuration(d.seconds)} de estudo, ${d.sets} teste(s)${d.average_score !== null ? `, nota média ${pct(d.average_score)}` : ""}`;
}

/**
 * Horas por dia (v1.5, interativo). Ponteiro fino: cada barra é um botão (passar o mouse ou focar
 * mostra o dia; clicar abre o que foi feito). Ponteiro grosso (resposta 04 do DS): as barras ficam só
 * visuais (aria-hidden) e um Select "Dia" abaixo do gráfico escolhe o dia, sem toque no dia errado.
 * Altura pela custom property --value (geometria em execução).
 */
export function HoursChart({
  daily,
  selected,
  onSelect,
  coarse = false,
}: {
  daily: Metrics["daily"];
  selected: string | null;
  onSelect: (date: string) => void;
  coarse?: boolean;
}) {
  const [hover, setHover] = React.useState<string | null>(null);
  const max = Math.max(3600, ...daily.map((d) => d.seconds));
  const shown = daily.find((d) => d.date === (hover ?? selected));
  const total = daily.reduce((a, d) => a + d.seconds, 0);

  return (
    <figure className="space-y-2">
      {shown ? (
        <Readout
          value={formatDuration(shown.seconds)}
          label={formatDayMonth(parseLocalDate(shown.date))}
          hint={`${shown.sets} teste(s)${shown.cards ? ` · ${shown.cards} card(s)` : ""}${shown.average_score !== null ? ` · nota média ${pct(shown.average_score)}` : ""}${coarse ? "" : " · clique para ver o dia"}`}
        />
      ) : (
        <Readout
          value={formatDuration(total)}
          label="no período"
          hint={coarse ? "Escolha um dia abaixo do gráfico" : "Passe o mouse ou clique numa barra"}
        />
      )}
      <div className="relative h-40 border-b border-border" onPointerLeave={() => setHover(null)}>
        {coarse ? (
          // Toque: barras só visuais; o Select "Dia" abaixo dá os mesmos dias e valores
          <div className="flex h-full items-end gap-px" aria-hidden="true">
            {daily.map((d) => (
              <div key={d.date} className="flex h-full min-w-0 flex-1 items-end px-[15%]">
                <Bar seconds={d.seconds} max={max} dim={!!selected && selected !== d.date} />
              </div>
            ))}
          </div>
        ) : (
          <ol className="flex h-full items-end gap-px" aria-label="Horas por dia">
            {daily.map((d) => (
              <li key={d.date} className="flex h-full min-w-0 flex-1">
                <button
                  type="button"
                  // Leitura completa (resposta 03 do DS): os botões são a fonte acessível dos números
                  aria-label={dayReading(d)}
                  aria-pressed={selected === d.date}
                  onPointerEnter={() => setHover(d.date)}
                  onFocus={() => setHover(d.date)}
                  onBlur={() => setHover(null)}
                  onClick={() => onSelect(d.date)}
                  className={cn(
                    "group flex h-full w-full items-end rounded-sm px-[15%] hover:bg-muted focus-visible:bg-muted",
                    focusRing,
                  )}
                >
                  <Bar seconds={d.seconds} max={max} dim={!!selected && selected !== d.date} />
                </button>
              </li>
            ))}
          </ol>
        )}
      </div>
      <figcaption className="flex justify-between text-xs text-muted-foreground">
        <span>{formatDayMonth(parseLocalDate(daily[0].date))}</span>
        <span>máx. {formatDuration(max)} por dia</span>
        <span>{formatDayMonth(parseLocalDate(daily[daily.length - 1].date))}</span>
      </figcaption>
      {coarse && (
        <Field id="hours-day" label="Dia">
          {() => (
            <Select
              id="hours-day"
              value={selected ?? ""}
              onValueChange={onSelect}
              placeholder="Escolha um dia para ver o que fez"
              // Mais recente primeiro; mesma leitura das barras
              options={[...daily].reverse().map((d) => ({ value: d.date, label: dayOption(d) }))}
            />
          )}
        </Field>
      )}
    </figure>
  );
}

/** Opção do Select "Dia": "Seg 10/11 — 2h30" (resposta 04 do DS) */
function dayOption(d: Metrics["daily"][number]) {
  const day = parseLocalDate(d.date);
  const wd = formatWeekdayShort(day);
  return `${wd.charAt(0).toUpperCase()}${wd.slice(1)} ${formatDayMonth(day)} — ${formatDuration(d.seconds)}${d.sets ? ` · ${d.sets} teste(s)` : ""}`;
}

function Bar({ seconds, max, dim }: { seconds: number; max: number; dim: boolean }) {
  return (
    <span
      style={{ "--value": `${(seconds / max) * 100}%` } as React.CSSProperties}
      className={cn(
        "block h-[var(--value)] w-full rounded-t-sm bg-chart-1 transition-opacity",
        seconds > 0 && "min-h-0.5",
        dim && "opacity-60",
      )}
    />
  );
}

/**
 * Notas dos testes em ordem (v1.5, interativo): linha em SVG e cada ponto um botão (alvo de 24 px,
 * marca de 8 px). Passar o mouse ou focar mostra o teste; clicar abre o teste no painel do agente.
 */
export function ScoresChart({
  scores,
  threshold,
  onOpen,
  coarse = false,
}: {
  scores: Metrics["scores"];
  threshold: number;
  onOpen: (setId: number) => void;
  coarse?: boolean;
}) {
  const [hover, setHover] = React.useState<number | null>(null);
  const pts = scores.filter((s) => s.score !== null);
  if (pts.length === 0) return <p className="text-sm text-muted-foreground">Nenhum teste concluído no período.</p>;
  // Coordenadas em % da área: x de 4% a 96%, y de 5% (100%) a 95% (0%)
  const x = (i: number) => (pts.length === 1 ? 50 : 4 + (i / (pts.length - 1)) * 92);
  const y = (v: number) => 95 - v * 90;
  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.score!)}`).join(" ");
  const shown = hover !== null ? pts[hover] : null;
  const avg = pts.reduce((a, p) => a + p.score!, 0) / pts.length;

  return (
    <figure className="space-y-2">
      {shown ? (
        <Readout
          value={pct(shown.score)}
          label={`${shown.label} · ${shown.topic ?? shown.subject ?? ""}`}
          hint={`${formatDayMonth(parseLocalDateTime(shown.date))} ${formatTime(parseLocalDateTime(shown.date))} · clique para abrir o teste`}
        />
      ) : (
        <Readout
          value={pct(avg)}
          label="nota média"
          hint={`${pts.length} teste(s) · ${coarse ? "toque num ponto para abrir o teste" : "passe o mouse ou clique num ponto"}`}
        />
      )}
      <div className="relative h-40" onPointerLeave={() => setHover(null)}>
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="absolute inset-0 h-full w-full"
          aria-hidden="true"
        >
          <line
            x1="0"
            x2="100"
            y1={y(threshold)}
            y2={y(threshold)}
            className="stroke-success-text"
            strokeWidth="1"
            strokeDasharray="3 2"
            vectorEffect="non-scaling-stroke"
          />
          <line
            x1="0"
            x2="100"
            y1="95"
            y2="95"
            className="stroke-border"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
          <path d={path} fill="none" className="stroke-chart-1" strokeWidth="2" vectorEffect="non-scaling-stroke" />
        </svg>
        {/* Rótulo do limiar em texto (resposta 03 do DS): a linha não fica só na cor */}
        <span
          aria-hidden="true"
          style={{ "--y": `${y(threshold)}%` } as React.CSSProperties}
          className="absolute left-0 top-[var(--y)] -translate-y-full pb-0.5 text-xs font-medium text-success-text"
        >
          {Math.round(threshold * 100)}%
        </span>
        <ol aria-label="Notas dos testes">
          {pts.map((p, i) => (
            <li key={p.set_id}>
              <button
                type="button"
                aria-label={`${p.topic ?? p.subject ?? "Teste"} (${p.label}), ${formatDayMonth(parseLocalDateTime(p.date))}: nota ${pct(p.score)}. Abrir o teste.`}
                onPointerEnter={() => setHover(i)}
                onFocus={() => setHover(i)}
                onBlur={() => setHover(null)}
                onClick={() => onOpen(p.set_id)}
                style={{ "--x": `${x(i)}%`, "--y": `${y(p.score!)}%` } as React.CSSProperties}
                className={cn(
                  "group absolute left-[var(--x)] top-[var(--y)] flex h-6 w-6 pointer-coarse:after:absolute pointer-coarse:after:left-1/2 pointer-coarse:after:top-1/2 pointer-coarse:after:size-11 pointer-coarse:after:-translate-1/2 pointer-coarse:after:content-[''] -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full",
                  focusRing,
                )}
              >
                <span
                  className={cn(
                    "block h-2 w-2 rounded-full bg-chart-1 ring-2 ring-card transition-transform group-hover:scale-150 group-focus-visible:scale-150",
                    hover === i && "scale-150",
                  )}
                />
              </button>
            </li>
          ))}
        </ol>
      </div>
      <figcaption className="flex justify-between text-xs text-muted-foreground">
        <span>{formatDayMonth(parseLocalDateTime(pts[0].date))}</span>
        <span>linha tracejada = {Math.round(threshold * 100)}% (aprendido)</span>
        <span>{formatDayMonth(parseLocalDateTime(pts[pts.length - 1].date))}</span>
      </figcaption>
    </figure>
  );
}
