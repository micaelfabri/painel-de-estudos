import { BookOpen, CheckCircle2, RotateCcw, XCircle } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { CategoryBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api, type CardReviewResult, type CardView } from "@/lib/api";
import { parseLocalDate } from "@/lib/format";
import { MISTAKE_STATUS } from "@/lib/mistakes";
import { cn } from "@/lib/utils";

const LETTERS = "ABCDEF";

/** Dias até a próxima revisão, para dizer "volta amanhã" / "volta em 7 dias" */
function inDays(next: string) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((parseLocalDate(next).getTime() - today.getTime()) / 86_400_000);
  if (days <= 0) return "volta hoje";
  return days === 1 ? "volta amanhã" : `volta em ${days} dias`;
}

/** Frase do resultado (D33): o que acontece com o erro de origem e quando o card volta */
function outcome(result: CardReviewResult, mode: "answer" | "flip") {
  const when = inDays(result.card.next_review);
  if (!result.card.mistake_id) return result.knew ? `Certo. O card ${when}.` : `Ainda não. O card ${when}.`;
  if (!result.knew) return `Este erro volta para "revisar de novo" e o card ${when}.`;
  if (mode === "answer") return `Acertou: o erro virou "corrigido". O card ${when}.`;
  return `Marcado como sabia. O card ${when}.`;
}

/** Onde rever: tema, página do Notion e minuto do vídeo quando houver */
function ReviewWhere({ card }: { card: CardView }) {
  return (
    <p className="flex items-start gap-2 text-xs text-muted-foreground">
      <BookOpen className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>
        Rever: {card.topic_title}
        {card.notion_url && (
          <>
            {" · "}
            <a
              href={card.notion_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary-text underline-offset-4 hover:underline"
            >
              página no Notion
            </a>
          </>
        )}
        {card.video_minute && ` · vídeo ${card.video_minute}`}
        {card.source_detail && ` · ${card.source_detail}`}
      </span>
    </p>
  );
}

/**
 * Um card de estudo (SPEC D33): Responder (4 alternativas) ou Virar (Sabia/Não sabia).
 * O resultado vai para a API, que muda o calendário do card e o erro de origem.
 */
export function CardReview({
  card,
  position,
  onAnswered,
  onNext,
  nextLabel = "Próximo card",
}: {
  card: CardView;
  position?: string;
  onAnswered?: (result: CardReviewResult) => void;
  onNext?: () => void;
  nextLabel?: string;
}) {
  const canAnswer = !!card.options && card.options.length >= 2 && card.correct_index !== null;
  const [mode, setMode] = React.useState<"answer" | "flip">(canAnswer ? card.mode : "flip");
  const [choice, setChoice] = React.useState("");
  const [flipped, setFlipped] = React.useState(false);
  const [result, setResult] = React.useState<CardReviewResult | null>(null);
  const [sending, setSending] = React.useState(false);
  const summaryRef = React.useRef<HTMLParagraphElement>(null);
  const groupId = `card-${card.id}`;

  React.useEffect(() => {
    if (result) summaryRef.current?.focus();
  }, [result]);

  const send = async (body: { mode: "answer" | "flip"; knew?: boolean; chosen_index?: number }) => {
    setSending(true);
    try {
      const res = await api.post<CardReviewResult>(`/cards/${card.id}/review`, body);
      setResult(res);
      onAnswered?.(res);
    } catch {
      toast.error("Não foi possível salvar a resposta do card.");
    } finally {
      setSending(false);
    }
  };

  const side = mode === "answer" ? "responder" : flipped ? "verso" : "frente";
  const status = card.mistake_status;

  return (
    <Card className="space-y-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {position ? `${position} · ` : ""}
          {side}
        </p>
        {status ? (
          <StatusBadge className={MISTAKE_STATUS[status].className} dotClassName={MISTAKE_STATUS[status].dot}>
            Do erro: {MISTAKE_STATUS[status].label.toLowerCase()}
          </StatusBadge>
        ) : (
          <CategoryBadge className="bg-muted text-foreground">{card.kind_label}</CategoryBadge>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        {card.subject_name} · {card.topic_title} · {card.source_label.toLowerCase()}
      </p>
      <p id={`${groupId}-front`} className={cn(mode === "flip" && !flipped ? "text-base" : "text-sm", "font-medium")}>
        {card.front}
      </p>

      {mode === "answer" && card.options && (
        <RadioGroup
          value={choice}
          onValueChange={setChoice}
          disabled={result !== null}
          aria-labelledby={`${groupId}-front`}
        >
          {card.options.map((opt, i) => {
            const isCorrect = result && i === result.correct_index;
            const isWrong = result && !result.knew && String(i) === choice;
            return (
              <label
                key={`${card.id}-${i}`}
                htmlFor={`${groupId}-${i}`}
                className={cn(
                  "flex min-h-11 items-start gap-3 rounded-md py-2 sm:min-h-0",
                  result ? "cursor-default" : "cursor-pointer",
                )}
              >
                <RadioGroupItem id={`${groupId}-${i}`} value={String(i)} className="mt-0.5" />
                <span className="flex-1 text-sm">
                  <span aria-hidden="true">{LETTERS[i]}) </span>
                  {opt}
                  {isCorrect && (
                    <span className="ml-2 inline-flex items-center gap-1 text-xs text-success-text">
                      <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                      Correta
                    </span>
                  )}
                  {isWrong && (
                    <span className="ml-2 inline-flex items-center gap-1 text-xs text-destructive-text">
                      <XCircle className="h-4 w-4" aria-hidden="true" />
                      Sua resposta
                    </span>
                  )}
                </span>
              </label>
            );
          })}
        </RadioGroup>
      )}

      {mode === "flip" && flipped && <p className="text-base font-medium">{card.back}</p>}

      <div aria-live="polite">
        {result && (
          <p ref={summaryRef} tabIndex={-1} className="text-sm font-medium focus:outline-none">
            {outcome(result, mode)}
          </p>
        )}
      </div>

      {(result || (mode === "flip" && flipped)) && (
        <>
          {(card.explanation || card.chosen_text) && (
            <div role="note" className="space-y-2 rounded-md border border-border bg-muted/50 p-3 text-sm">
              {card.explanation && <p>{card.explanation}</p>}
              {card.chosen_text && (
                <p className="text-muted-foreground">Quando errou, você marcou "{card.chosen_text}".</p>
              )}
            </div>
          )}
          <ReviewWhere card={card} />
        </>
      )}

      {result ? (
        onNext && <Button onClick={onNext}>{nextLabel}</Button>
      ) : mode === "answer" ? (
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => send({ mode: "answer", chosen_index: Number(choice) })}
            disabled={choice === "" || sending}
          >
            Responder
          </Button>
          <Button variant="ghost" onClick={() => setMode("flip")}>
            Prefiro virar
          </Button>
        </div>
      ) : flipped ? (
        <div className="flex gap-3">
          <Button
            variant="secondary"
            className="flex-1"
            disabled={sending}
            onClick={() => send({ mode: "flip", knew: false })}
          >
            Não sabia
          </Button>
          <Button className="flex-1" disabled={sending} onClick={() => send({ mode: "flip", knew: true })}>
            Sabia
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">Pense na resposta antes de virar.</p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setFlipped(true)}>
              <RotateCcw aria-hidden="true" />
              Virar card
            </Button>
            {canAnswer && (
              <Button variant="ghost" onClick={() => setMode("answer")}>
                Responder com alternativas
              </Button>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
