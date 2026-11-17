import { History, Sparkles } from "lucide-react";
import * as React from "react";
import { Link } from "react-router-dom";

import { useAgent } from "@/components/agent/AgentContext";
import { CategoryBadge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import type { ReviewReasonKey, ReviewResponse, ReviewSubject, Semester, SettingsResponse } from "@/lib/api";
import { useApi } from "@/lib/useApi";

const ALL = "all";
const REASON_STYLE: Record<ReviewReasonKey, string> = {
  failed: "bg-destructive/10 text-destructive-text",
  not_learned: "bg-warning/10 text-warning-text",
  not_consolidated: "bg-warning/10 text-warning-text",
  not_seen_all: "bg-muted text-foreground",
};
const ORDER: ReviewReasonKey[] = ["failed", "not_learned", "not_consolidated", "not_seen_all"];

function SubjectReview({ s, nOptions }: { s: ReviewSubject; nOptions: number }) {
  const { startSet, pending } = useAgent();
  const hint = `review-hint-${s.id}`;
  return (
    <li>
      <Card className="space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-base font-semibold">{s.name}</h3>
          <span className="text-xs text-muted-foreground">{s.status === "failed" ? "Reprovada" : "Aprovada"}</span>
        </div>
        <ul className="space-y-2" aria-label={`Motivos da revisão de ${s.name}`}>
          {s.reasons.map((r) => (
            <li key={r.key} className="flex flex-wrap items-baseline gap-2 text-sm">
              <CategoryBadge className={REASON_STYLE[r.key]}>{r.label}</CategoryBadge>
              <span className="text-muted-foreground">{r.detail}</span>
            </li>
          ))}
        </ul>
        {s.topics.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Temas para rever</p>
            <ul className="divide-y divide-border text-sm">
              {s.topics.map((t) => (
                <li key={t.id} className="flex flex-wrap items-baseline justify-between gap-x-3 py-1">
                  <span className="min-w-0">{t.title}</span>
                  <span className="text-xs text-muted-foreground">{t.why.join(" · ")}</span>
                </li>
              ))}
            </ul>
            {s.more_topics > 0 && <p className="text-xs text-muted-foreground">e mais {s.more_topics} tema(s).</p>}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!s.has_text || pending !== null}
            aria-describedby={!s.has_text ? hint : undefined}
            onClick={() =>
              startSet({
                userText: `Gerar questões de ${s.name} inteira.`,
                pendingLabel: "Gerando questões da disciplina…",
                path: "/agent/question-sets/subject",
                body: { subject_id: s.id, n_options: nOptions },
              })
            }
          >
            <Sparkles aria-hidden="true" />
            Questões da disciplina
          </Button>
          <Link to="/estudo/historico" className={buttonVariants({ variant: "ghost", size: "sm" })}>
            <History aria-hidden="true" />
            Ver no histórico
          </Link>
          {!s.has_text && (
            <p id={hint} className="text-xs text-muted-foreground">
              Nenhum tema com texto salvo nem página do Notion: ligue as páginas em Gerenciar → Temas.
            </p>
          )}
        </div>
      </Card>
    </li>
  );
}

/** v1.9 (D51): semestres em revisão — disciplinas encerradas que pedem revisão, com o motivo */
export function ReviewPage() {
  const [semester, setSemester] = React.useState(ALL);
  const semesters = useApi<Semester[]>("/semesters");
  const settings = useApi<SettingsResponse>("/settings");
  const data = useApi<ReviewResponse>(semester === ALL ? "/review" : `/review?semester_id=${semester}`);
  const nOptions = Number(settings.data?.values.options_per_question ?? 5) || 5;
  const groups = data.data?.semesters ?? [];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">Revisão</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Disciplinas encerradas (aprovadas ou reprovadas) que pedem revisão, por semestre. Os motivos saem dos
            testes, dos retestes, dos erros e do progresso no portal.
          </p>
        </div>
        <div className="w-full sm:w-64">
          <Field id="r-semester" label="Semestre">
            {() => (
              <Select
                id="r-semester"
                value={semester}
                onValueChange={setSemester}
                options={[
                  { value: ALL, label: "Todos os semestres" },
                  ...[...(semesters.data ?? [])]
                    .sort((a, b) => b.code.localeCompare(a.code))
                    .map((x) => ({ value: String(x.id), label: x.code + (x.is_current ? " (atual)" : "") })),
                ]}
              />
            )}
          </Field>
        </div>
      </header>

      {data.error ? (
        <p role="alert" className="text-sm text-destructive-text">
          Não foi possível carregar a revisão: {data.error}
        </p>
      ) : data.data && groups.length === 0 ? (
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">
            Nada em revisão. Quando uma disciplina for marcada como aprovada ou reprovada, ela aparece aqui se ficou
            algo para trás.
          </p>
        </Card>
      ) : (
        groups.map((g) => {
          const id = `h-sem-${g.semester_id ?? "none"}`;
          const summary = ORDER.filter((k) => g.counts[k])
            .map((k) => `${g.counts[k]} ${(data.data?.reasons[k] ?? k).toLowerCase()}`)
            .join(" · ");
          return (
            <section key={id} aria-labelledby={id} className="space-y-3">
              <div className="space-y-1">
                <h2 id={id} className="text-lg font-semibold">
                  {g.code ? `Semestre ${g.code}${g.is_current ? " (atual)" : ""}` : "Sem semestre"}
                  <span className="font-normal text-muted-foreground"> · em revisão</span>
                </h2>
                <p className="text-sm text-muted-foreground">
                  {g.subjects.length} disciplina(s) · {summary}
                </p>
              </div>
              <ul className="grid gap-4 lg:grid-cols-2">
                {g.subjects.map((s) => (
                  <SubjectReview key={s.id} s={s} nOptions={nOptions} />
                ))}
              </ul>
            </section>
          );
        })
      )}
    </div>
  );
}
