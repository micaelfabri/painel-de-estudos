import * as React from "react";

import { RecordList } from "@/components/manage/RecordList";
import { Pagination } from "@/components/ui/pagination";
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

const STATUS: Record<string, string> = {
  ok: "ok",
  invalid_json: "JSON inválido",
  error: "erro",
  cancelled: "cancelada",
};

interface UsagePage {
  page: number;
  pages: number;
  per_page: number;
  total: number;
  items: LlmCallRow[];
}

/** Registro de uso do modelo (SPEC §7): modelo, prompt, tokens, tempo, status; 10 por página (v1.7) */
export function UsageLog() {
  const [page, setPage] = React.useState(1);
  const calls = useApi<UsagePage>(`/agent/usage?page=${page}&per_page=10`);
  const heading = React.useRef<HTMLHeadingElement>(null);
  // Resposta 06 do DS: ao trocar de página, o foco vai para o início da lista
  const goTo = (p: number) => {
    setPage(p);
    requestAnimationFrame(() => {
      heading.current?.focus({ preventScroll: true });
      heading.current?.scrollIntoView?.({ block: "start" });
    });
  };
  return (
    <section aria-labelledby="h-uso" className="space-y-3">
      <h2 id="h-uso" ref={heading} tabIndex={-1} className="scroll-mt-20 text-lg font-semibold focus:outline-none">
        Registro de uso do modelo
      </h2>
      <RecordList
        caption="Chamadas ao modelo local"
        rows={calls.data?.items ?? []}
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
            cell: (c) =>
              c.error ? `${STATUS[c.status] ?? c.status}: ${c.error.slice(0, 80)}` : (STATUS[c.status] ?? c.status),
            inCard: true,
          },
        ]}
        actions={() => null}
      />
      {calls.data && (
        <Pagination
          page={calls.data.page}
          pages={calls.data.pages}
          total={calls.data.total}
          onPage={goTo}
          label="Páginas do registro de uso"
        />
      )}
    </section>
  );
}
