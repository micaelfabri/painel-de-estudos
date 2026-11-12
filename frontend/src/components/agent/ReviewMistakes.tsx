import { CheckCircle2, XCircle } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, type Mistake, type MistakeReview } from "@/lib/api";

const LETTERS = "ABCDEF";

/** Revisar erros: cada questão errada com a resposta dada, a correta, a explicação e o minuto do vídeo */
export function ReviewMistakes({ onClose }: { onClose: () => void }) {
  const [items, setItems] = React.useState<MistakeReview[] | null>(null);

  React.useEffect(() => {
    api
      .get<MistakeReview[]>("/learning/mistakes")
      .then(setItems)
      .catch(() => setItems([]));
  }, []);

  const markReviewed = async (m: MistakeReview) => {
    try {
      const current = await api.get<Mistake>(`/mistakes/${m.id}`);
      await api.put(`/mistakes/${m.id}`, { ...current, reviewed: true });
      setItems((list) => (list ?? []).filter((x) => x.id !== m.id));
      toast.success("Erro marcado como revisado");
    } catch {
      toast.error("Não foi possível marcar como revisado.");
    }
  };

  return (
    <section aria-labelledby="h-revisar" className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 id="h-revisar" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Revisar erros {items && items.length > 0 && `(${items.length})`}
        </h3>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Voltar
        </Button>
      </div>
      {items === null && <p className="text-sm text-muted-foreground">Carregando…</p>}
      {items?.length === 0 && <p className="text-sm text-muted-foreground">Nenhum erro para revisar.</p>}
      {items?.map((m) => (
        <Card key={m.id} className="space-y-3 p-4">
          <p className="text-xs text-muted-foreground">
            {m.subject_name} · {m.topic_title}
            {m.video_minute && ` · vídeo ${m.video_minute}`}
          </p>
          <p className="text-sm font-medium">{m.statement}</p>
          {m.chosen_index !== null && (
            <p className="flex items-start gap-2 text-sm">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive-text" aria-hidden="true" />
              <span>
                <span className="text-destructive-text">Sua resposta: </span>
                {LETTERS[m.chosen_index]}) {m.options[m.chosen_index]}
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
          <Button variant="outline" size="sm" onClick={() => markReviewed(m)}>
            Marcar como revisado
          </Button>
        </Card>
      ))}
    </section>
  );
}
