import * as React from "react";

import { CardReview } from "@/components/cards/CardReview";
import { Card, CardContent, CardEyebrow } from "@/components/ui/card";
import type { CardView } from "@/lib/api";
import { useApi } from "@/lib/useApi";

/**
 * Card do dia (SPEC D37): um card no Painel, do ponto mais fraco da disciplina com a prova mais
 * próxima. Responde aqui mesmo; o mesmo card fica o dia todo.
 */
export function CardOfDay({ onAnswered }: { onAnswered?: () => void }) {
  const today = useApi<{ card: CardView | null; answered: boolean }>("/cards/today");
  const [done, setDone] = React.useState(false);
  const card = today.data?.card;
  if (!card) return null;

  return (
    <section aria-labelledby="h-card-dia" className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="h-card-dia" className="text-lg font-semibold">
          Card do dia
        </h2>
        <p className="text-xs text-muted-foreground">{card.subject_name}</p>
      </div>
      {today.data?.answered && !done ? (
        <Card>
          <CardContent className="space-y-1">
            <CardEyebrow>Respondido hoje</CardEyebrow>
            <p className="text-sm">{card.front}</p>
            <p className="text-xs text-muted-foreground">Amanhã tem outro.</p>
          </CardContent>
        </Card>
      ) : (
        <CardReview
          card={card}
          onAnswered={() => {
            setDone(true);
            onAnswered?.();
          }}
        />
      )}
    </section>
  );
}
