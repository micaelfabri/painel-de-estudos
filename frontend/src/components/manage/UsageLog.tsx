import { RecordList } from "@/components/manage/RecordList";
import { formatNumber } from "@/lib/format";
import { useApi } from "@/lib/useApi";

interface LlmCallRow {
  id: number;
  created_at: string | null;
  model: string;
  prompt: string;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number;
  attempts: number;
  status: string;
  error: string | null;
}

const STATUS: Record<string, string> = { ok: "ok", invalid_json: "JSON inválido", error: "erro", cancelled: "cancelada" };

/** Registro de uso do modelo (SPEC §7): modelo, prompt, tokens, tempo, status */
export function UsageLog() {
  const calls = useApi<LlmCallRow[]>("/agent/usage");
  return (
    <section aria-labelledby="h-uso" className="space-y-3">
      <h2 id="h-uso" className="text-lg font-semibold">
        Registro de uso do modelo
      </h2>
      <RecordList
        caption="Chamadas ao modelo local"
        rows={calls.data ?? []}
        rowKey={(c) => c.id}
        title={(c) => `${c.created_at?.replace("T", " ").slice(0, 16) ?? "—"} · ${c.model}`}
        empty="Nenhuma chamada ao modelo ainda."
        columns={[
          { header: "Prompt", cell: (c) => c.prompt },
          {
            header: "Tokens (entrada/saída)",
            cell: (c) => `${c.input_tokens ?? "—"} / ${c.output_tokens ?? "—"}`,
            numeric: true,
            inCard: true,
          },
          { header: "Tempo", cell: (c) => `${formatNumber(c.latency_ms / 1000, 1)} s`, numeric: true, inCard: true },
          { header: "Tentativas", cell: (c) => c.attempts, numeric: true },
          {
            header: "Status",
            cell: (c) => (c.error ? `${STATUS[c.status] ?? c.status}: ${c.error.slice(0, 80)}` : (STATUS[c.status] ?? c.status)),
            inCard: true,
          },
        ]}
        actions={() => null}
      />
    </section>
  );
}
