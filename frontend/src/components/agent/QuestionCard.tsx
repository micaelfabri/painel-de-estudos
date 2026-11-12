import { CheckCircle2, Flag, XCircle } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api, type AnswerResult, type QuestionView } from "@/lib/api";
import { cn } from "@/lib/utils";

const LETTERS = "ABCDEF";

interface Props {
  question: QuestionView;
  index: number;
  total: number;
  onAnswered: (result: AnswerResult, chosenIndex: number) => void;
  onFlagged: (setScore: number | null) => void;
  onNext: () => void;
}

/** Card de questão de múltipla escolha (DS v2.13) */
export function QuestionCard({ question, index, total, onAnswered, onFlagged, onNext }: Props) {
  const [choice, setChoice] = React.useState<string>("");
  const [sending, setSending] = React.useState(false);
  const summaryRef = React.useRef<HTMLParagraphElement>(null);
  const answer = question.answer;
  const groupId = `q-${question.id}`;

  React.useEffect(() => {
    setChoice(answer ? String(answer.chosen_index) : "");
  }, [question.id, answer]);

  React.useEffect(() => {
    if (answer) summaryRef.current?.focus();
  }, [answer]);

  const submit = async () => {
    setSending(true);
    try {
      const chosen = Number(choice);
      onAnswered(await api.post<AnswerResult>(`/agent/questions/${question.id}/answer`, { chosen_index: chosen }), chosen);
    } catch {
      toast.error("Não foi possível registrar a resposta.");
    } finally {
      setSending(false);
    }
  };

  const flag = async () => {
    try {
      const res = await api.post<{ set_score: number | null }>(`/agent/questions/${question.id}/flag`, {});
      onFlagged(res.set_score);
      toast.success("Questão marcada como ruim. Ela não conta na nota.");
    } catch {
      toast.error("Não foi possível marcar a questão.");
    }
  };

  const isLast = index === total - 1;

  return (
    <Card className="space-y-4 p-6">
      <p className="text-xs text-muted-foreground">
        Questão {index + 1} de {total}
      </p>
      <p id={`${groupId}-statement`} className="text-sm font-medium">
        {question.statement}
      </p>

      <RadioGroup value={choice} onValueChange={setChoice} disabled={answer !== null} aria-labelledby={`${groupId}-statement`}>
        {question.options.map((opt, i) => {
          const isCorrect = answer && i === answer.correct_index;
          const isWrongChoice = answer && !answer.is_correct && i === answer.chosen_index;
          return (
            <label
              key={`${question.id}-${i}`}
              htmlFor={`${groupId}-${i}`}
              className={cn(
                "flex min-h-11 items-start gap-3 rounded-md py-2 sm:min-h-0",
                answer ? "cursor-default" : "cursor-pointer",
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
                {isWrongChoice && (
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

      <div aria-live="polite">
        {answer && (
          <p ref={summaryRef} tabIndex={-1} className="text-sm font-medium focus:outline-none">
            {answer.is_correct ? "Você acertou." : `Resposta errada. A correta é a ${LETTERS[answer.correct_index]}.`}
          </p>
        )}
      </div>
      {answer?.explanation && (
        <div role="note" className="rounded-md border border-border bg-muted/50 p-3 text-sm">
          {answer.explanation}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {answer ? (
          <Button onClick={onNext}>{isLast ? "Ver resultado" : "Próxima"}</Button>
        ) : (
          <Button onClick={submit} disabled={choice === "" || sending}>
            Responder
          </Button>
        )}
        {!question.flagged_bad && (
          <Button variant="ghost" onClick={flag}>
            <Flag aria-hidden="true" />
            Marcar questão ruim
          </Button>
        )}
      </div>
    </Card>
  );
}
