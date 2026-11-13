import { Flame } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { useAgent } from "@/components/agent/AgentContext";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, type Area, type CardReviewResult, type CardView } from "@/lib/api";
import { useArea } from "@/lib/area";
import { CardReview } from "./CardReview";

/** Tempo da rodada: "4 min 12 s" (a rodada costuma durar poucos minutos) */
function roundTime(seconds: number) {
  const total = Math.max(0, Math.round(seconds));
  const m = Math.floor(total / 60);
  return m ? `${m} min ${total % 60} s` : `${total} s`;
}

/** Abre uma rodada rápida (D37): até 10 cards dos pontos fracos, vencidos primeiro */
export async function startRound(
  openCards: ReturnType<typeof useAgent>["openCards"],
  subjectId?: number | null,
  area: Area = "faculdade",
) {
  try {
    const cards = await api.post<CardView[]>("/cards/round", { size: 10, subject_id: subjectId ?? null, area });
    openCards({ title: "Rodada rápida", cards, round: true });
    return true;
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "Não foi possível montar a rodada.");
    return false;
  }
}

/** Abre os cards vencidos hoje (de um tema ou de tudo) */
export async function startDue(
  openCards: ReturnType<typeof useAgent>["openCards"],
  topicId?: number,
  title = "Cards para revisar",
  area: Area = "faculdade",
) {
  try {
    const query = topicId ? `topic_id=${topicId}&due=true` : `due=true&area=${area}`;
    let cards = await api.get<CardView[]>(`/cards?${query}&limit=30`);
    if (cards.length === 0 && topicId) cards = await api.get<CardView[]>(`/cards?topic_id=${topicId}&limit=30`);
    if (cards.length === 0) {
      toast.info("Nenhum card vencido hoje.");
      return false;
    }
    openCards({ title, cards });
    return true;
  } catch {
    toast.error("Não foi possível abrir os cards.");
    return false;
  }
}

/** Sessão de cards no painel do agente: um por vez; na rodada rápida, tempo, sequência e resultado */
export function CardSessionView() {
  const { cardSession, closeCards, openCards, bumpLearning } = useAgent();
  // v1.8: "Nova rodada" fica na área da página aberta (faculdade ou cursos)
  const area = useArea();
  const [index, setIndex] = React.useState(0);
  const [results, setResults] = React.useState<{ card: CardView; knew: boolean }[]>([]);
  const [startedAt] = React.useState(() => Date.now());
  const [endedAt, setEndedAt] = React.useState<number | null>(null);
  const resultRef = React.useRef<HTMLHeadingElement>(null);

  const done = endedAt !== null;
  React.useEffect(() => {
    if (done) resultRef.current?.focus();
  }, [done]);

  if (!cardSession) return null;
  const { cards, round, title } = cardSession;
  const card = cards[index];
  const right = results.filter((r) => r.knew).length;
  let best = 0;
  let run = 0;
  for (const r of results) {
    run = r.knew ? run + 1 : 0;
    best = Math.max(best, run);
  }
  const current = results.length && results[results.length - 1].knew ? run : 0;

  const answered = (res: CardReviewResult) => setResults((list) => [...list, { card: res.card, knew: res.knew }]);
  const next = () => {
    if (index + 1 < cards.length) setIndex(index + 1);
    else {
      setEndedAt(Date.now());
      bumpLearning();
    }
  };

  return (
    <section aria-labelledby="h-cards" className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 id="h-cards" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {title}
        </h3>
        <Button variant="ghost" size="sm" onClick={closeCards}>
          Fechar
        </Button>
      </div>
      {round && !done && results.length > 0 && (
        <p className="flex items-center gap-2 text-xs text-muted-foreground" aria-live="polite">
          <Flame className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          {right} de {results.length} · sequência de {current}
        </p>
      )}

      {done ? (
        <Card className="space-y-4 p-6">
          <div className="flex items-center justify-between gap-2">
            <h4 ref={resultRef} tabIndex={-1} className="text-xs text-muted-foreground focus:outline-none">
              {round ? `Rodada rápida · ${cards.length} cards` : `Revisão · ${cards.length} cards`}
            </h4>
            <StatusBadge className="bg-success/10 text-success-text">Concluída</StatusBadge>
          </div>
          <p className="text-2xl font-semibold tabular-nums">
            {right} de {results.length}
            {round && (
              <span className="text-sm font-normal text-muted-foreground">
                {" "}
                em {roundTime(((endedAt ?? startedAt) - startedAt) / 1000)}
              </span>
            )}
          </p>
          {round && (
            <p className="flex items-center gap-2 text-sm">
              <Flame className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              Maior sequência: {best} seguido{best === 1 ? "" : "s"}
            </p>
          )}
          {results.some((r) => !r.knew) && (
            <div className="space-y-1">
              <p className="text-sm font-medium">Para rever (vencem amanhã)</p>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {results
                  .filter((r) => !r.knew)
                  .map((r) => (
                    <li key={r.card.id}>
                      {r.card.front} · {r.card.topic_title}
                    </li>
                  ))}
              </ul>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            {round && <Button onClick={() => void startRound(openCards, null, area)}>Nova rodada</Button>}
            <Button variant={round ? "ghost" : "default"} onClick={closeCards}>
              Fechar
            </Button>
          </div>
        </Card>
      ) : (
        card && (
          <CardReview
            key={card.id}
            card={card}
            position={`Card ${index + 1} de ${cards.length}`}
            onAnswered={answered}
            onNext={next}
            nextLabel={index + 1 < cards.length ? "Próximo card" : "Ver resultado"}
          />
        )
      )}
    </section>
  );
}
