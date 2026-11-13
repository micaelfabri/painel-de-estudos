import type { MistakeCounts, MistakeStatus } from "@/lib/api";

/** Ciclo dos erros (SPEC D28): não revisado → revisado → corrigido ou revisar de novo */
// Badge de status (rounded-full com ponto); `dot` só quando o ponto não usa a cor do texto
export const MISTAKE_STATUS: Record<MistakeStatus, { label: string; className: string; dot?: string }> = {
  open: { label: "Não revisado", className: "bg-muted text-foreground", dot: "bg-muted-foreground" },
  reviewed: { label: "Revisado", className: "bg-primary/10 text-primary-text" },
  again: { label: "Revisar de novo", className: "bg-warning/10 text-warning-text" },
  fixed: { label: "Corrigido", className: "bg-success/10 text-success-text" },
};

/** Resumo em texto: "3 não revisados · 1 revisado · 7 corrigidos" (só o que tem) */
export function mistakeSummary(c: MistakeCounts) {
  const parts = [
    c.open && `${c.open} não revisado${c.open > 1 ? "s" : ""}`,
    c.reviewed && `${c.reviewed} revisado${c.reviewed > 1 ? "s" : ""}`,
    c.again && `${c.again} para revisar de novo`,
    c.fixed && `${c.fixed} corrigido${c.fixed > 1 ? "s" : ""}`,
  ].filter(Boolean);
  return parts.join(" · ");
}
