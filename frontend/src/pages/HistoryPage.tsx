import { FolderOpen, Layers, Repeat, Sparkles, Timer } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { useAgent } from "@/components/agent/AgentContext";
import { startDue } from "@/components/cards/CardSessionView";
import { mistakeSummary } from "@/lib/mistakes";
import { RecordList } from "@/components/manage/RecordList";
import { CategoryBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { type HistorySet, type SettingsResponse, type TopicEvolution, type Area } from "@/lib/api";
import { formatDayMonth, formatTime, parseLocalDate, parseLocalDateTime } from "@/lib/format";
import { usePaged } from "@/lib/usePaged";
import { AREA_TEXT, useAreaSubjects } from "@/lib/area";
import { useApi } from "@/lib/useApi";
import { cn } from "@/lib/utils";

const STATUS: Record<TopicEvolution["status"], { label: string; className: string }> = {
  learned: { label: "Aprendido", className: "bg-success/10 text-success-text" },
  review: { label: "Revisar", className: "bg-warning/10 text-warning-text" },
  pending: { label: "Em andamento", className: "bg-muted text-foreground" },
};

const pct = (score: number | null) => (score === null ? "—" : `${Math.round(score * 100)}%`);

/** Data do conjunto: concluído (hora local) ou criado (o SQLite grava em UTC) */
function setWhen(s: HistorySet) {
  const d = s.completed_at ? parseLocalDateTime(s.completed_at) : s.created_at ? new Date(`${s.created_at}Z`) : null;
  return d ? `${formatDayMonth(d)} ${formatTime(d)}` : "—";
}

/**
 * Estudo › Histórico (SPEC D15, D16): tudo o que já fiz fica salvo, com refazer e novos testes.
 * v1.8 (D38): a mesma página serve a faculdade e os cursos (`area`).
 */
export function HistoryPage({ area = "faculdade" }: { area?: Area }) {
  const { startSet, openSet, learningVersion, pending, openCards } = useAgent();
  const [subjectFilter, setSubjectFilter] = React.useState("all");
  const sets = useApi<HistorySet[]>(`/study/history?limit=500&area=${area}`);
  const topics = useApi<TopicEvolution[]>(`/study/history/topics?area=${area}`);
  const text = AREA_TEXT[area];
  const areaSubjects = useAreaSubjects(area);
  const settings = useApi<SettingsResponse>("/settings");
  const [simSubject, setSimSubject] = React.useState("");

  React.useEffect(() => {
    void sets.reload();
    void topics.reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [learningVersion]);

  const nOptions = Number(settings.data?.values.options_per_question ?? 5) || 5;
  const subjects = areaSubjects;
  const filterOptions = [
    { value: "all", label: text.allSubjects },
    ...subjects.map((s) => ({ value: String(s.id), label: s.name })),
  ];
  const byFilter = <T extends { subject_id: number | null }>(rows: T[]) =>
    subjectFilter === "all" ? rows : rows.filter((r) => String(r.subject_id) === subjectFilter);

  // v1.7.2: 10 por página nas duas listas; a página volta para 1 ao trocar a disciplina
  const topicPages = usePaged(byFilter(topics.data ?? []), subjectFilter);
  const setPages = usePaged(byFilter(sets.data ?? []), subjectFilter);

  const open = async (id: number) => {
    try {
      await openSet(id);
      toast.success("Aberto no painel do agente");
    } catch {
      toast.error("Não foi possível abrir o conjunto.");
    }
  };

  const busy = pending !== null;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{area === "cursos" ? "Histórico dos cursos" : "Histórico"}</h1>
          <p className="text-sm text-muted-foreground">
            Todos os testes ficam salvos aqui. Refaça as erradas ou peça um teste novo com base nos erros ou nos
            acertos.
          </p>
        </div>
        <div className="w-full sm:w-64">
          <Field id="h-filter" label={text.subject}>
            {() => (
              <Select id="h-filter" value={subjectFilter} onValueChange={setSubjectFilter} options={filterOptions} />
            )}
          </Field>
        </div>
      </header>

      <Card className="space-y-4 p-6">
        <div className="flex items-center gap-2">
          <Timer className="h-5 w-5 text-primary-text" aria-hidden="true" />
          <h2 className="text-lg font-semibold">Simulado da prova</h2>
        </div>
        <p className="text-sm text-muted-foreground">
          Mistura os temas da disciplina que já têm texto salvo, no tamanho da prova, com tempo correndo. Quando o tempo
          acaba, entrega sozinho.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-full sm:w-72">
            <Field id="sim-subject" label={`${text.subject} do simulado`}>
              {() => (
                <Select
                  id="sim-subject"
                  value={simSubject}
                  onValueChange={setSimSubject}
                  placeholder="Escolha"
                  options={subjects.map((s) => ({
                    value: String(s.id),
                    label: s.name,
                  }))}
                />
              )}
            </Field>
          </div>
          <Button
            disabled={!simSubject || busy}
            onClick={() =>
              startSet({
                userText: "Fazer o simulado da prova.",
                pendingLabel: "Montando o simulado…",
                path: "/agent/simulations",
                body: { subject_id: Number(simSubject), n_options: nOptions },
              })
            }
          >
            <Timer aria-hidden="true" />
            Fazer simulado
          </Button>
        </div>
      </Card>

      <section className="space-y-3" aria-labelledby="h-temas">
        <div className="space-y-1">
          <h2
            id="h-temas"
            ref={topicPages.anchor as React.RefObject<HTMLHeadingElement>}
            tabIndex={-1}
            className="scroll-mt-20 text-lg font-semibold focus:outline-none"
          >
            Evolução por tema
          </h2>
          <p className="text-sm text-muted-foreground">
            O tema vira Aprendido com 70% ou mais no reteste de 7 dias. Se o reteste de 21 dias ficar abaixo de 70%,
            volta para Revisar. Refazer erradas e os testes novos não mudam o status.
          </p>
        </div>
        {byFilter(topics.data ?? []).length === 0 ? (
          <Card className="p-6">
            <p className="text-sm text-muted-foreground">Nenhum tema com teste concluído ainda.</p>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {topicPages.slice.map((t) => (
              <Card key={t.topic_id} className="space-y-3 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs text-muted-foreground">{t.subject_name}</p>
                    <h3 className="text-sm font-semibold">{t.topic_title}</h3>
                  </div>
                  <CategoryBadge className={STATUS[t.status].className}>{STATUS[t.status].label}</CategoryBadge>
                </div>
                <ol className="flex flex-wrap gap-2" aria-label="Notas em ordem">
                  {t.points.map((p) => (
                    <li key={p.set_id}>
                      <button
                        type="button"
                        onClick={() => open(p.set_id)}
                        title={`${p.label} · ${formatDayMonth(parseLocalDate(p.date))}`}
                        className={cn(
                          "rounded-md border border-border px-2 py-1 text-xs tabular-nums hover:bg-muted",
                          p.score !== null && p.score >= 0.7 ? "text-success-text" : "text-foreground",
                        )}
                      >
                        {pct(p.score)}
                        <span className="sr-only">
                          {" "}
                          {p.label} em {formatDayMonth(parseLocalDate(p.date))}
                        </span>
                      </button>
                    </li>
                  ))}
                </ol>
                {mistakeSummary(t.mistakes) && (
                  <p className="text-xs text-muted-foreground">Erros: {mistakeSummary(t.mistakes)}</p>
                )}
                {t.cards > 0 && <p className="text-xs text-muted-foreground">{t.cards} card(s) deste tema</p>}
                <div className="flex flex-wrap gap-2">
                  {t.cards > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        void startDue(openCards, t.topic_id, `Cards · ${t.topic_title}`).then(
                          (ok) => ok && toast.success("Aberto no painel do agente"),
                        )
                      }
                    >
                      <Layers aria-hidden="true" />
                      Revisar cards
                    </Button>
                  )}
                  {t.mistakes.open + t.mistakes.reviewed + t.mistakes.again > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={busy}
                      onClick={() =>
                        startSet({
                          userText: `Refazer os erros não corrigidos de ${t.topic_title}.`,
                          pendingLabel: "Separando os erros…",
                          path: "/agent/mistakes/redo",
                          body: { topic_id: t.topic_id },
                        })
                      }
                    >
                      <Repeat aria-hidden="true" />
                      Refazer erros
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy || !t.has_text}
                    onClick={() =>
                      startSet({
                        userText: `Novo teste de ${t.topic_title} com base nos meus erros.`,
                        pendingLabel: "Gerando questões sobre os erros…",
                        path: "/agent/question-sets/focus",
                        body: {
                          topic_id: t.topic_id,
                          focus: "errors",
                          n_options: nOptions,
                        },
                      })
                    }
                  >
                    <Sparkles aria-hidden="true" />
                    Novo teste: erros
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy || !t.has_text}
                    onClick={() =>
                      startSet({
                        userText: `Novo teste de ${t.topic_title} com base nos meus acertos.`,
                        pendingLabel: "Gerando questões sobre os acertos…",
                        path: "/agent/question-sets/focus",
                        body: {
                          topic_id: t.topic_id,
                          focus: "hits",
                          n_options: nOptions,
                        },
                      })
                    }
                  >
                    <Sparkles aria-hidden="true" />
                    Novo teste: acertos
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
        <Pagination
          page={topicPages.page}
          pages={topicPages.pages}
          total={topicPages.total}
          onPage={topicPages.goTo}
          label="Páginas da evolução por tema"
        />
      </section>

      <section className="space-y-3" aria-labelledby="h-testes">
        <h2
          id="h-testes"
          ref={setPages.anchor as React.RefObject<HTMLHeadingElement>}
          tabIndex={-1}
          className="scroll-mt-20 text-lg font-semibold focus:outline-none"
        >
          Todos os testes
        </h2>
        <RecordList
          caption="Todos os testes"
          rows={setPages.slice}
          rowKey={(s) => s.id}
          title={(s) => s.topic_title}
          empty="Nenhum teste ainda. Gere questões no painel do agente."
          columns={[
            { header: "Quando", cell: setWhen, inCard: true },
            { header: "Tipo", cell: (s) => s.label, inCard: true },
            {
              header: "Resultado",
              numeric: true,
              inCard: true,
              cell: (s) =>
                s.completed_at
                  ? `${pct(s.score)} (${s.right} de ${s.questions})`
                  : `em andamento · ${s.answered} de ${s.questions}`,
            },
            { header: "Disciplina", cell: (s) => s.subject_name ?? "—" },
          ]}
          actions={(s) => (
            <div className="flex gap-1">
              <Button variant="ghost" size="sm" onClick={() => open(s.id)}>
                <FolderOpen aria-hidden="true" />
                {s.completed_at ? "Ver" : "Continuar"}
              </Button>
              {s.completed_at && s.wrong > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  onClick={() =>
                    startSet({
                      userText: `Refazer as ${s.wrong} erradas de ${s.topic_title}.`,
                      pendingLabel: "Separando as erradas…",
                      path: `/agent/question-sets/${s.id}/redo`,
                      body: {},
                    })
                  }
                >
                  <Repeat aria-hidden="true" />
                  Refazer erradas
                </Button>
              )}
            </div>
          )}
        />
        <Pagination
          page={setPages.page}
          pages={setPages.pages}
          total={setPages.total}
          onPage={setPages.goTo}
          label="Páginas de todos os testes"
        />
      </section>
    </div>
  );
}
