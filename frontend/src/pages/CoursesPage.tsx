import { ExternalLink, GraduationCap, Plus } from "lucide-react";
import * as React from "react";
import { Link, useNavigate } from "react-router-dom";

import { CourseDialog, COURSE_STATUSES } from "@/components/courses/CourseDialog";
import { InlineMeter } from "@/components/panel/InlineMeter";
import { CategoryBadge } from "@/components/ui/badge";
import { Button, buttonVariants, focusRing } from "@/components/ui/button";
import { Card, CardContent, CardEyebrow } from "@/components/ui/card";
import type { Course, CourseStatus, CoursesSummary } from "@/lib/api";
import { formatDayMonth, formatDuration, parseLocalDate, parseLocalDateTime } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { cn } from "@/lib/utils";

const inDays = (n: number) => (n === 0 ? "hoje" : n === 1 ? "amanhã" : n < 0 ? `há ${-n} dias` : `em ${n} dias`);

/** Selo do card: prova (certificação) > meta de data > carga semanal; prazo perto em aviso */
function CourseBadge({ c }: { c: Course }) {
  if (c.course_status === "done")
    return (
      <CategoryBadge className="bg-success/10 text-success-text">
        Concluído{c.finished_on ? ` em ${formatDayMonth(parseLocalDate(c.finished_on))}` : ""}
      </CategoryBadge>
    );
  if (c.exam_at && c.days_to_exam !== null && c.days_to_exam >= 0)
    return (
      <CategoryBadge className={c.days_to_exam <= 14 ? "bg-warning/10 text-warning-text" : "bg-muted text-foreground"}>
        Prova {formatDayMonth(parseLocalDateTime(c.exam_at))} · {inDays(c.days_to_exam)}
      </CategoryBadge>
    );
  if (c.target_date && c.days_to_target !== null)
    return (
      <CategoryBadge
        className={
          c.days_to_target >= 0 && c.days_to_target <= 14
            ? "bg-warning/10 text-warning-text"
            : "bg-muted text-foreground"
        }
      >
        Meta {formatDayMonth(parseLocalDate(c.target_date))} · {inDays(c.days_to_target)}
      </CategoryBadge>
    );
  return <CategoryBadge className="bg-muted text-foreground">Sem meta de data</CategoryBadge>;
}

function CourseCard({ c }: { c: Course }) {
  const progressLabel = c.modules_total ? "módulos concluídos" : "progresso informado";
  return (
    <Card className="flex flex-col gap-4 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">
            {c.platform ? `${c.platform} · ` : ""}
            {c.type_label}
          </p>
          <h2 className="text-base font-semibold">
            <Link to={`/cursos/${c.id}`} className={cn("rounded-sm hover:underline", focusRing)}>
              {c.name}
            </Link>
          </h2>
        </div>
        <CourseBadge c={c} />
      </div>
      <div>
        <p className="text-2xl font-semibold tabular-nums">{c.progress}%</p>
        <p className="text-xs text-muted-foreground">{progressLabel}</p>
      </div>
      <InlineMeter label={`Progresso de ${c.name}`} value={c.progress} hideLabel />
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {c.modules_total > 0 && (
          <div className="min-w-0">
            <dt className="text-xs text-muted-foreground">módulos</dt>
            <dd className="text-sm tabular-nums">
              {c.modules_done}/{c.modules_total}
            </dd>
          </div>
        )}
        <div className="min-w-0">
          <dt className="text-xs text-muted-foreground">horas</dt>
          <dd className="text-sm tabular-nums">
            {formatDuration(c.seconds)}
            {c.total_hours ? ` / ${c.total_hours}h` : ""}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="text-xs text-muted-foreground">esta semana</dt>
          <dd className="text-sm tabular-nums">{formatDuration(c.week_seconds)}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-xs text-muted-foreground">{c.counts_acc ? "AAC" : "testes"}</dt>
          <dd className="text-sm tabular-nums">
            {c.counts_acc
              ? c.acc_activity_id
                ? "lançada"
                : c.total_hours
                  ? `${c.total_hours}h ao concluir`
                  : "sim"
              : c.sets}
          </dd>
        </div>
      </dl>
      {c.next_lesson && c.course_status !== "done" && (
        <p className="text-sm">
          <span className="text-muted-foreground">Próximo: </span>
          {c.next_lesson.title ? `${c.next_lesson.module} · ${c.next_lesson.title}` : c.next_lesson.module}
        </p>
      )}
      <div className="mt-auto flex flex-wrap gap-2">
        <Link to={`/cursos/${c.id}`} className={buttonVariants({ variant: "outline", size: "sm" })}>
          <GraduationCap aria-hidden="true" />
          Ver curso
        </Link>
        {c.url && (
          <a
            href={c.url}
            target="_blank"
            rel="noopener noreferrer"
            className={buttonVariants({ variant: "ghost", size: "sm" })}
          >
            <ExternalLink aria-hidden="true" />
            Abrir {c.platform ? `no ${c.platform}` : "o curso"}
            <span className="sr-only"> (abre em outra aba)</span>
          </a>
        )}
      </div>
    </Card>
  );
}

/** Abas por situação (visual de TabsList do DS); setas do teclado trocam de aba */
function StatusTabs({
  value,
  counts,
  onChange,
}: {
  value: CourseStatus;
  counts: Record<CourseStatus, number> | undefined;
  onChange: (v: CourseStatus) => void;
}) {
  const refs = React.useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (i + step + COURSE_STATUSES.length) % COURSE_STATUSES.length;
    refs.current[next]?.focus();
    onChange(COURSE_STATUSES[next].value);
  };
  return (
    <div className="max-w-full overflow-x-auto p-2">
      <div role="tablist" aria-label="Situação dos cursos" className="inline-flex w-auto rounded-md bg-muted p-1">
        {COURSE_STATUSES.map((s, i) => {
          const active = s.value === value;
          return (
            <button
              key={s.value}
              ref={(el) => {
                refs.current[i] = el;
              }}
              type="button"
              role="tab"
              id={`tab-${s.value}`}
              aria-selected={active}
              aria-controls="courses-panel"
              tabIndex={active ? 0 : -1}
              onClick={() => onChange(s.value)}
              onKeyDown={(e) => onKey(e, i)}
              className={cn(
                "inline-flex h-11 shrink-0 items-center justify-center whitespace-nowrap rounded-sm px-3 text-sm font-medium transition-colors duration-150 sm:h-8",
                active ? "bg-card text-foreground" : "text-muted-foreground hover:text-foreground",
                focusRing,
              )}
            >
              {s.label} ({counts?.[s.value] ?? 0})
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** v1.8 (D38, D39): Cursos e certificados › Meus cursos */
export function CoursesPage() {
  const [status, setStatus] = React.useState<CourseStatus>("doing");
  const [creating, setCreating] = React.useState(false);
  const courses = useApi<Course[]>(`/courses?status=${status}`);
  const summary = useApi<CoursesSummary>("/courses/summary");
  const navigate = useNavigate();
  const s = summary.data;
  const goal = s?.goal_hours ?? null;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Meus cursos</h1>
          <p className="text-sm text-muted-foreground">
            Cursos livres, certificações e idiomas, fora da faculdade. O Painel continua só com a faculdade.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus aria-hidden="true" />
          Novo curso
        </Button>
      </header>

      <section aria-label="Resumo dos cursos" className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent>
            <CardEyebrow>Horas em cursos</CardEyebrow>
            <p className="text-2xl font-semibold tabular-nums">{s ? formatDuration(s.week_seconds) : "—"}</p>
            <p className="text-xs text-muted-foreground">esta semana{goal ? ` · meta ${goal}h` : ""}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <CardEyebrow>Certificados</CardEyebrow>
            <p className="text-2xl font-semibold tabular-nums">{s?.certificates ?? "—"}</p>
            <p className="text-xs text-muted-foreground">
              concluídos{s?.acc_hours ? ` · ${s.acc_hours}h lançadas como AAC` : ""}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <CardEyebrow>Próxima prova</CardEyebrow>
            <p className="text-2xl font-semibold tabular-nums">
              {s?.next_exam ? formatDayMonth(parseLocalDateTime(s.next_exam.exam_at)) : "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {s?.next_exam ? `${s.next_exam.name} · ${inDays(s.next_exam.days)}` : "nenhuma certificação marcada"}
            </p>
          </CardContent>
        </Card>
      </section>

      <StatusTabs value={status} counts={s?.counts} onChange={setStatus} />

      <div id="courses-panel" role="tabpanel" aria-labelledby={`tab-${status}`}>
        {courses.error ? (
          <p role="alert" className="text-sm text-destructive-text">
            Não foi possível carregar os cursos: {courses.error}
          </p>
        ) : courses.data && courses.data.length === 0 ? (
          <Card className="p-6">
            <p className="text-sm text-muted-foreground">
              {status === "doing"
                ? 'Nenhum curso em andamento. Use "Novo curso" para cadastrar um.'
                : "Nenhum curso nesta situação."}
            </p>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {(courses.data ?? []).map((c) => (
              <CourseCard key={c.id} c={c} />
            ))}
          </div>
        )}
      </div>

      <CourseDialog
        open={creating}
        onOpenChange={setCreating}
        onSaved={(c) => {
          void summary.reload();
          navigate(`/cursos/${c.id}`);
        }}
      />
    </div>
  );
}
