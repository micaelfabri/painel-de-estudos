import { CheckCircle2, Repeat, XCircle } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { api, type MistakeCounts, type MistakeReview } from "@/lib/api";
import { useArea } from "@/lib/area";
import { usePaged } from "@/lib/usePaged";
import { MISTAKE_STATUS, mistakeSummary } from "@/lib/mistakes";
import { useAgent } from "./AgentContext";

const LETTERS = "ABCDEF";

const FILTERS: { value: string; label: string; status: string }[] = [
  { value: "todo", label: "Ainda não corrigidos", status: "open,reviewed,again" },
  { value: "open", label: "Não revisados e revisar de novo", status: "open,again" },
  { value: "reviewed", label: "Revisados (falta acertar)", status: "reviewed" },
  { value: "fixed", label: "Corrigidos", status: "fixed" },
];

/**
 * Revisar erros: cada questão errada com a resposta dada, a correta, a explicação e o minuto do vídeo.
 * "Já revisei" marca como revisado; "Refazer" monta um conjunto com os erros ainda não corrigidos e as
 * respostas decidem: acertou → corrigido; errou → revisar de novo.
 */
export function ReviewMistakes({ onClose }: { onClose: () => void }) {
  const { startSet, pending, learningVersion } = useAgent();
  // v1.8 (D38): os erros da área da página aberta (faculdade ou cursos)
  const area = useArea();
  const [filter, setFilter] = React.useState("todo");
  const [items, setItems] = React.useState<MistakeReview[] | null>(null);
  const [counts, setCounts] = React.useState<MistakeCounts | null>(null);

  const status = FILTERS.find((f) => f.value === filter)!.status;
  const load = React.useCallback(() => {
    api
      .get<MistakeReview[]>(`/learning/mistakes?status=${status}&area=${area}`)
      .then(setItems)
      .catch(() => setItems([]));
    api
      .get<MistakeCounts>(`/learning/mistakes/summary?area=${area}`)
      .then(setCounts)
      .catch(() => setCounts(null));
  }, [status, area]);

  React.useEffect(() => load(), [load, learningVersion]);

  const markReviewed = async (m: MistakeReview) => {
    try {
      await api.patch(`/learning/mistakes/${m.id}`, { status: "reviewed" });
      toast.success("Marcado como revisado. Refaça para confirmar que aprendeu.");
      load();
    } catch {
      toast.error("Não foi possível marcar como revisado.");
    }
  };

  const unfixed = counts ? counts.open + counts.reviewed + counts.again : 0;
  // v1.7.2: 10 erros por página; volta para a 1 ao trocar o filtro
  const paged = usePaged(items ?? [], filter);

  return (
    <section aria-labelledby="h-revisar" className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3
          id="h-revisar"
          ref={paged.anchor as React.RefObject<HTMLHeadingElement>}
          tabIndex={-1}
          className="scroll-mt-4 text-xs font-medium uppercase tracking-wider text-muted-foreground focus:outline-none"
        >
          Revisar erros
        </h3>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Voltar
        </Button>
      </div>
      {counts && <p className="text-xs text-muted-foreground">{mistakeSummary(counts) || "Nenhum erro ainda."}</p>}
      <Button
        variant="outline"
        size="sm"
        disabled={unfixed === 0 || pending !== null}
        onClick={() =>
          startSet({
            userText: "Refazer os erros que ainda não corrigi.",
            pendingLabel: "Separando os erros…",
            path: "/agent/mistakes/redo",
            body: { area },
          })
        }
      >
        <Repeat aria-hidden="true" />
        Refazer erros não corrigidos{unfixed > 0 && ` (${Math.min(unfixed, 10)})`}
      </Button>
      <Field id="mistake-filter" label="Mostrar">
        {() => <Select id="mistake-filter" value={filter} onValueChange={setFilter} options={FILTERS} />}
      </Field>

      {items === null && <p className="text-sm text-muted-foreground">Carregando…</p>}
      {items?.length === 0 && <p className="text-sm text-muted-foreground">Nenhum erro aqui.</p>}
      {paged.slice.map((m) => (
        <Card key={m.id} className="space-y-3 p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="text-xs text-muted-foreground">
              {m.subject_name} · {m.topic_title}
              {m.video_minute && ` · vídeo ${m.video_minute}`}
            </p>
            <StatusBadge className={MISTAKE_STATUS[m.status].className} dotClassName={MISTAKE_STATUS[m.status].dot}>
              {MISTAKE_STATUS[m.status].label}
            </StatusBadge>
          </div>
          <p className="text-sm font-medium">{m.statement}</p>
          {m.chosen_index !== null && m.chosen_index >= 0 && (
            <p className="flex items-start gap-2 text-sm">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive-text" aria-hidden="true" />
              <span>
                <span className="text-destructive-text">Sua resposta: </span>
                {LETTERS[m.chosen_index]}) {m.options[m.chosen_index]}
              </span>
            </p>
          )}
          {m.chosen_index === -1 && (
            // Simulado que acabou o tempo (ou "Entregar agora"): a questão ficou sem resposta
            <p className="flex items-start gap-2 text-sm">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive-text" aria-hidden="true" />
              <span>
                <span className="text-destructive-text">Sua resposta: </span>
                não respondida (o tempo acabou ou o teste foi entregue antes)
              </span>
            </p>
          )}
          <p className="flex items-start gap-2 text-sm">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success-text" aria-hidden="true" />
            <span>
              <span className="text-success-text">Correta: </span>
              {LETTERS[m.correct_index]}) {m.options[m.correct_index]}
            </span>
          </p>
          {m.explanation && (
            <div role="note" className="rounded-md border border-border bg-muted/50 p-3 text-sm">
              {m.explanation}
            </div>
          )}
          {(m.status === "open" || m.status === "again") && (
            <Button variant="outline" size="sm" onClick={() => markReviewed(m)}>
              Já revisei
            </Button>
          )}
          {m.status === "reviewed" && (
            <p className="text-xs text-muted-foreground">Revisado. Acerte num refazer para virar corrigido.</p>
          )}
        </Card>
      ))}
      <Pagination
        page={paged.page}
        pages={paged.pages}
        total={paged.total}
        onPage={paged.goTo}
        label="Páginas dos erros"
      />
    </section>
  );
}
