import { CheckCircle2 } from "lucide-react";
import type { CSSProperties } from "react";

import { cn } from "@/lib/utils";

interface InlineMeterProps {
  label: string;
  /** 0–100 */
  value: number;
  /** Limiar em % (ex.: 70 = aprendido). Sem limiar, a barra é só progresso neutro. */
  threshold?: number;
  thresholdLabel?: string;
  hideLabel?: boolean;
  className?: string;
}

/** Medidor em linha (DS v2.13): rótulo · barra h-2 · valor; marca de limiar; "Aprendido" no limiar ou acima */
export function InlineMeter({ label, value, threshold, thresholdLabel = "Aprendido", hideLabel, className }: InlineMeterProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const reached = threshold !== undefined && clamped >= threshold;
  const valueText =
    threshold === undefined
      ? `${Math.round(clamped)}%`
      : reached
        ? `${Math.round(clamped)}%, ${thresholdLabel.toLowerCase()}`
        : `${Math.round(clamped)}%, abaixo de ${threshold}% para ${thresholdLabel.toLowerCase()}`;

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <span className={cn("min-w-0 shrink-0 text-sm", hideLabel && "sr-only")}>{label}</span>
      <div
        role="meter"
        aria-label={label}
        aria-valuenow={Math.round(clamped)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuetext={valueText}
        className="relative h-2 flex-1 rounded-full bg-muted"
        style={{ "--value": `${clamped}%`, "--threshold": `${threshold ?? 0}%` } as CSSProperties}
      >
        <div
          className={cn(
            "h-2 w-[var(--value)] rounded-full",
            threshold === undefined ? "bg-primary" : reached ? "bg-success" : "bg-muted-foreground",
          )}
        />
        {threshold !== undefined && (
          <div aria-hidden="true" className="absolute -top-1 left-[var(--threshold)] h-4 w-[2px] bg-foreground/40" />
        )}
      </div>
      <span className="shrink-0 text-sm tabular-nums">{Math.round(clamped)}%</span>
      {reached && (
        <span className="inline-flex shrink-0 items-center gap-1 text-xs text-success-text">
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          {thresholdLabel}
        </span>
      )}
    </div>
  );
}
