import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, type Mistake, type QuestionSetView } from "@/lib/api";
import { useAgent } from "./AgentContext";
import { QuestionCard } from "./QuestionCard";

/** Questões do conjunto ativo, uma por vez; no fim, nota e pontos para rever no vídeo */
export function QuestionFlow({ onFinished }: { onFinished?: () => void }) {
  const { activeSet, setActiveSet, pushEntry } = useAgent();
  const [index, setIndex] = React.useState(0);
  const [showResult, setShowResult] = React.useState(false);

  React.useEffect(() => {
    if (!activeSet) return;
    const firstOpen = activeSet.questions.findIndex((q) => q.answer === null && !q.flagged_bad);
    setIndex(firstOpen === -1 ? activeSet.questions.length - 1 : firstOpen);
    setShowResult(activeSet.completed_at !== null && firstOpen === -1);
    // Só ao trocar de conjunto
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSet?.id]);

  if (!activeSet) return null;
  const questions = activeSet.questions;

  const patch = (fn: (s: QuestionSetView) => QuestionSetView) => setActiveSet(fn(activeSet));

  const next = () => {
    const after = questions.findIndex((q, i) => i > index && q.answer === null && !q.flagged_bad);
    if (after !== -1) setIndex(after);
    else {
      setShowResult(true);
      const valid = questions.filter((q) => !q.flagged_bad);
      const right = valid.filter((q) => q.answer?.is_correct).length;
      pushEntry({
        role: "agent",
        kind: "result",
        text: `Você acertou ${right} de ${valid.length} (${Math.round((right / Math.max(1, valid.length)) * 100)}%) em ${activeSet.topic_title}.`,
      });
      onFinished?.();
    }
  };

  const finishNow = async () => {
    try {
      const done = await api.post<QuestionSetView>(`/agent/question-sets/${activeSet.id}/finish`, {});
      setActiveSet(done);
      setShowResult(true);
      const valid = done.questions.filter((q) => !q.flagged_bad);
      const right = valid.filter((q) => q.answer?.is_correct).length;
      pushEntry({
        role: "agent",
        kind: "result",
        text: `${done.label ?? "Conjunto"} entregue: ${right} de ${valid.length} (${Math.round((right / Math.max(1, valid.length)) * 100)}%). As não respondidas contam como erradas.`,
      });
      onFinished?.();
    } catch {
      toast.error("Não foi possível entregar o conjunto.");
    }
  };

  if (showResult) return <ResultCard set={activeSet} />;

  const q = questions[index];
  return (
    <div className="space-y-3">
      {activeSet.seconds_left != null && !activeSet.completed_at ? (
        <Countdown key={activeSet.id} seconds={activeSet.seconds_left} onEnd={finishNow} />
      ) : null}
      <QuestionCard
        question={q}
        index={index}
        total={questions.length}
        onAnswered={(res, chosen) =>
          patch((s) => ({
            ...s,
            score: res.set_score,
            questions: s.questions.map((x) =>
              x.id === q.id
                ? {
                    ...x,
                    answer: {
                      chosen_index: chosen,
                      is_correct: res.is_correct,
                      correct_index: res.correct_index,
                      explanation: res.explanation,
                    },
                  }
                : x,
            ),
          }))
        }
        onFlagged={(score) =>
          patch((s) => ({
            ...s,
            score,
            questions: s.questions.map((x) => (x.id === q.id ? { ...x, flagged_bad: true } : x)),
          }))
        }
        onNext={next}
      />
    </div>
  );
}

/** Contagem regressiva do simulado (D16): no fim, entrega sozinho */
function Countdown({ seconds, onEnd }: { seconds: number; onEnd: () => void }) {
  const [endsAt] = React.useState(() => Date.now() + seconds * 1000);
  const [now, setNow] = React.useState(() => Date.now());
  const ended = React.useRef(false);
  React.useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const left = Math.max(0, Math.round((endsAt - now) / 1000));
  React.useEffect(() => {
    if (left === 0 && !ended.current) {
      ended.current = true;
      onEnd();
    }
  }, [left, onEnd]);
  const mm = String(Math.floor(left / 60)).padStart(2, "0");
  const ss = String(left % 60).padStart(2, "0");
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2">
      <p className="text-sm">
        Tempo restante:{" "}
        <span className={`font-semibold tabular-nums ${left < 300 ? "text-destructive-text" : ""}`}>
          {mm}:{ss}
        </span>
      </p>
      <Button variant="outline" size="sm" onClick={onEnd}>
        Entregar agora
      </Button>
    </div>
  );
}

/** Resultado: % de acerto e, para cada erro, o minuto do vídeo para rever */
function ResultCard({ set }: { set: QuestionSetView }) {
  const [mistakes, setMistakes] = React.useState<Mistake[]>([]);

  React.useEffect(() => {
    api.get<Mistake[]>(set.topic_id ? `/mistakes?topic_id=${set.topic_id}` : "/mistakes").then((list) => {
      const ids = new Set(set.questions.map((q) => q.id));
      setMistakes(list.filter((m) => ids.has(m.question_id)));
    });
  }, [set]);

  const saveMinute = async (m: Mistake, minute: string) => {
    try {
      const saved = await api.put<Mistake>(`/mistakes/${m.id}`, {
        ...m,
        video_minute: minute.trim() || null,
      });
      setMistakes((list) => list.map((x) => (x.id === m.id ? saved : x)));
    } catch {
      toast.error("Não foi possível salvar o minuto do vídeo.");
    }
  };

  const valid = set.questions.filter((q) => !q.flagged_bad);
  const right = valid.filter((q) => q.answer?.is_correct).length;

  return (
    <Card className="space-y-4 p-6">
      <div>
        <p className="text-2xl font-semibold tabular-nums">{Math.round((right / Math.max(1, valid.length)) * 100)}%</p>
        <p className="text-xs text-muted-foreground">
          {right} de {valid.length} certas em {set.topic_title}
          {valid.length < set.questions.length && ` · ${set.questions.length - valid.length} marcadas como ruins`}
        </p>
        {set.attempt_type === "redo" && (
          // D28: no refazer, cada resposta muda o erro da questão original
          <p className="mt-2 text-sm">
            {right} erro(s) corrigido(s)
            {valid.length - right > 0 && ` · ${valid.length - right} para revisar de novo`}. Veja em Revisar erros.
          </p>
        )}
      </div>
      {mistakes.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Pontos para rever no vídeo
          </h3>
          <ul className="space-y-3">
            {mistakes.map((m) => {
              const q = set.questions.find((x) => x.id === m.question_id);
              return (
                <li key={m.id} className="space-y-2">
                  <p className="text-sm">
                    Questão {q?.position}: {q?.statement}
                  </p>
                  <label htmlFor={`minute-${m.id}`} className="text-xs text-muted-foreground">
                    Minuto do vídeo (opcional)
                  </label>
                  <Input
                    id={`minute-${m.id}`}
                    defaultValue={m.video_minute ?? ""}
                    placeholder="ex.: 05:40"
                    onBlur={(e) => e.target.value !== (m.video_minute ?? "") && saveMinute(m, e.target.value)}
                  />
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Card>
  );
}
