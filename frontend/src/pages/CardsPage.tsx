import { FileUp, Layers, Plus, Send, Zap } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { useAgent } from "@/components/agent/AgentContext";
import { CardSourcesDialog } from "@/components/cards/CardSourcesDialog";
import { startDue, startRound } from "@/components/cards/CardSessionView";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { agentErrorMessage, api, type Area, type CardsSummary, type CardView } from "@/lib/api";
import { AREA_TEXT, useAreaSubjects } from "@/lib/area";
import { usePaged } from "@/lib/usePaged";
import { useApi } from "@/lib/useApi";

type Generated = { topic_id: number; topic_title: string; cards: CardView[] };

/** Estudo › Cards (SPEC D32–D37): cards feitos a partir do que mais erro. v1.8: também na área de cursos */
export function CardsPage({ area = "faculdade" }: { area?: Area }) {
  const summary = useApi<CardsSummary>(`/cards/summary?area=${area}`);
  const areaSubjects = useAreaSubjects(area);
  const text = AREA_TEXT[area];
  const { openCards, model, learningVersion } = useAgent();
  const [scope, setScope] = React.useState("weak");
  const [busy, setBusy] = React.useState<string | null>(null);
  const [sourcesOpen, setSourcesOpen] = React.useState(false);
  const [notionFor, setNotionFor] = React.useState<CardsSummary["topics"][number] | null>(null);
  const reload = summary.reload;
  React.useEffect(() => {
    if (learningVersion > 0) void reload();
  }, [learningVersion, reload]);

  const subjects = areaSubjects;
  const s = summary.data;
  // v1.7.2: lista por tema em páginas de 10
  const topicPages = usePaged(s?.topics ?? []);

  const generate = async (body: Record<string, unknown>, label: string) => {
    setBusy(label);
    try {
      const out = await api.post<Generated>("/cards/generate", { ...body, area, model });
      if (out.cards.length) toast.success(`${out.cards.length} cards criados: ${out.topic_title}`);
      else toast.info(`Nenhum card novo em ${out.topic_title}: o modelo repetiu cards que você já tem.`);
      if (out.cards.length) openCards({ title: `Cards novos · ${out.topic_title}`, cards: out.cards });
      void reload();
    } catch (err) {
      toast.error(agentErrorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const generateFromScope = () =>
    generate(
      scope === "weak" ? { scope: "weak" } : { scope: "subject", subject_id: Number(scope) },
      "O modelo está montando os cards dos seus pontos fracos…",
    );

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{area === "cursos" ? "Cards dos cursos" : "Cards"}</h1>
          <p className="text-sm text-muted-foreground">
            Feitos a partir do que você mais erra.
            {s && ` ${s.due} para revisar hoje · ${s.total} no total.`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={!s?.due}
            onClick={() => void startDue(openCards, undefined, undefined, area)}
          >
            <Layers aria-hidden="true" />
            Revisar vencidos{s?.due ? ` (${s.due})` : ""}
          </Button>
          <Button variant="outline" disabled={!s?.total} onClick={() => void startRound(openCards, null, area)}>
            <Zap aria-hidden="true" />
            Rodada rápida (10)
          </Button>
        </div>
      </header>

      <Card className="space-y-4 p-6">
        <h2 className="text-base font-semibold">Gerar cards</h2>
        <div className="flex flex-wrap items-end gap-4">
          <div className="w-full sm:w-72">
            <Field id="cards-scope" label="Dos pontos fracos de">
              {() => (
                <Select
                  id="cards-scope"
                  value={scope}
                  onValueChange={setScope}
                  options={[
                    { value: "weak", label: text.allSubjects },
                    ...subjects.map((x) => ({ value: String(x.id), label: x.name })),
                  ]}
                />
              )}
            </Field>
          </div>
          <Button onClick={generateFromScope} disabled={busy !== null}>
            <Plus aria-hidden="true" />
            Gerar cards dos meus pontos fracos
          </Button>
          <Button variant="outline" onClick={() => setSourcesOpen(true)} disabled={busy !== null}>
            <FileUp aria-hidden="true" />
            De prints ou de vídeo
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Começa pelos erros "revisar de novo" e "não revisado", depois os temas abaixo de 70%. Cada geração faz 10
          cards com o modelo local.
        </p>
        {busy && (
          <p role="status" className="text-sm text-muted-foreground">
            {busy}
          </p>
        )}
      </Card>

      <section aria-labelledby="h-cards-topics" className="space-y-3">
        <h2
          id="h-cards-topics"
          ref={topicPages.anchor as React.RefObject<HTMLHeadingElement>}
          tabIndex={-1}
          className="scroll-mt-20 focus:outline-none text-lg font-semibold"
        >
          Por tema
        </h2>
        {summary.error && (
          <p role="alert" className="text-sm text-destructive-text">
            {summary.error}
          </p>
        )}
        {s && s.topics.length === 0 ? (
          <Card className="p-6">
            <p className="text-sm text-muted-foreground">
              Nenhum card ainda. Faça um teste de um tema e depois gere os cards dos seus pontos fracos.
            </p>
          </Card>
        ) : (
          <Card>
            <ul className="divide-y divide-border">
              {topicPages.slice.map((t) => (
                <li key={t.topic_id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:gap-3">
                  <span className="min-w-0 flex-1 text-sm">
                    <span className="block font-medium">
                      {t.subject_name} · {t.topic_title}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {t.total} cards · {t.due} para hoje
                      {t.reviews > 0 && ` · sabia ${t.knew} de ${t.reviews} revisões`}
                    </span>
                  </span>
                  <div className="flex flex-wrap gap-1">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void startDue(openCards, t.topic_id, `Cards · ${t.topic_title}`)}
                    >
                      Revisar
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={busy !== null}
                      onClick={() =>
                        generate({ scope: "topic", topic_id: t.topic_id }, `Gerando mais cards de ${t.topic_title}…`)
                      }
                    >
                      Gerar mais
                    </Button>
                    {t.has_notion && (
                      <Button variant="ghost" size="sm" onClick={() => setNotionFor(t)}>
                        <Send aria-hidden="true" />
                        Notion
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}
        <Pagination
          page={topicPages.page}
          pages={topicPages.pages}
          total={topicPages.total}
          onPage={topicPages.goTo}
          label="Páginas dos cards por tema"
        />
      </section>

      <CardSourcesDialog
        open={sourcesOpen}
        onOpenChange={setSourcesOpen}
        subjects={subjects}
        onCreated={(cards, skipped) => {
          toast.success(`${cards.length} cards criados${skipped ? ` · ${skipped} imagem(ns) sem card` : ""}`);
          if (cards.length) openCards({ title: "Cards novos", cards });
          void reload();
        }}
      />
      <ConfirmDialog
        open={notionFor !== null}
        onOpenChange={(v) => !v && setNotionFor(null)}
        title={`Mandar os cards de "${notionFor?.topic_title ?? ""}" para o Notion?`}
        note="Os cards que ainda não foram enviados entram no fim da página do tema, como blocos que abrem e fecham. Nada na página é apagado."
        confirmLabel="Mandar para o Notion"
        onConfirm={async () => {
          if (!notionFor) return;
          const out = await api.post<{ sent: number }>(`/cards/topics/${notionFor.topic_id}/notion`, {});
          toast.success(out.sent ? `${out.sent} cards enviados para o Notion` : "Nenhum card novo para enviar");
        }}
      />
    </div>
  );
}
