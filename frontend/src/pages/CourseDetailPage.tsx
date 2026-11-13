import { Award, ExternalLink, FileText, Layers, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import * as React from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { useAgent } from "@/components/agent/AgentContext";
import { startDue } from "@/components/cards/CardSessionView";
import { CourseDialog } from "@/components/courses/CourseDialog";
import { TimerCard } from "@/components/panel/TimerCard";
import { StatusBadge } from "@/components/ui/badge";
import { Button, buttonVariants, focusRing } from "@/components/ui/button";
import { Card, CardContent, CardEyebrow } from "@/components/ui/card";
import { CheckboxRow } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import {
  agentErrorMessage,
  api,
  type CardView,
  type Course,
  type CourseLesson,
  type CourseModule,
  type SettingsResponse,
} from "@/lib/api";
import { formatDayMonth, formatDuration, parseLocalDate, parseLocalDateTime } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { cn } from "@/lib/utils";

const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);

const MODULE_STATUS: Record<string, { label: string; className: string; dot: string }> = {
  passed: { label: "Concluído", className: "bg-success/10 text-success-text", dot: "bg-success" },
  in_progress: { label: "Em andamento", className: "bg-accent text-accent-foreground", dot: "bg-primary" },
  pending: { label: "Não iniciado", className: "bg-muted text-foreground", dot: "bg-muted-foreground" },
};

/** Texto da aula: é dele que saem as questões e os cards (como o texto do tema na faculdade) */
function LessonTextDialog({
  lesson,
  onClose,
  onSaved,
}: {
  lesson: CourseLesson | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [text, setText] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => {
    if (!lesson) return;
    setText("");
    api
      .get<{ source_text: string | null }>(`/topics/${lesson.id}`)
      .then((t) => setText(t.source_text ?? ""))
      .catch(() => setText(""));
  }, [lesson]);
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lesson) return;
    setBusy(true);
    try {
      await api.patch(`/courses/lessons/${lesson.id}`, { source_text: text });
      toast.success("Texto da aula salvo");
      onSaved();
      onClose();
    } catch {
      toast.error("Não foi possível salvar o texto.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={lesson !== null} onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent
        title={lesson ? `Texto da aula: ${lesson.title}` : "Texto da aula"}
        description="Cole o conteúdo da aula (transcrição, resumo ou leitura). As questões e os cards saem dele."
      >
        <form onSubmit={save} className="space-y-4">
          <Field id="lesson-text" label="Texto">
            {() => <Textarea id="lesson-text" rows={10} value={text} onChange={(e) => setText(e.target.value)} />}
          </Field>
          <div className="flex gap-3">
            <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" className="flex-1" disabled={busy}>
              Salvar texto
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ModuleCard({
  module,
  nOptions,
  onChanged,
  onEditText,
}: {
  module: CourseModule;
  nOptions: number;
  onChanged: () => void;
  onEditText: (l: CourseLesson) => void;
}) {
  const { startSet, pending, openCards, model } = useAgent();
  const [open, setOpen] = React.useState(module.status !== "passed");
  const [newLesson, setNewLesson] = React.useState("");
  const [busy, setBusy] = React.useState<string | null>(null);
  const st = MODULE_STATUS[module.status] ?? MODULE_STATUS.pending;
  const listId = `module-${module.id}-lessons`;

  const toggleLesson = async (l: CourseLesson, done: boolean) => {
    try {
      await api.patch(`/courses/lessons/${l.id}`, { done });
      onChanged();
    } catch {
      toast.error("Não foi possível marcar a aula.");
    }
  };
  const toggleModule = async () => {
    try {
      await api.patch(`/courses/modules/${module.id}`, { done: module.status !== "passed" });
      onChanged();
    } catch {
      toast.error("Não foi possível mudar o módulo.");
    }
  };
  const addLesson = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLesson.trim()) return;
    try {
      await api.post(`/courses/modules/${module.id}/lessons`, { title: newLesson.trim() });
      setNewLesson("");
      onChanged();
    } catch {
      toast.error("Não foi possível adicionar a aula.");
    }
  };
  const generateCards = async () => {
    setBusy("O modelo está montando os cards do módulo…");
    try {
      const out = await api.post<{ topic_title: string; cards: CardView[] }>("/cards/generate", {
        scope: "subject",
        subject_id: module.id,
        area: "cursos",
        model,
      });
      if (out.cards.length) {
        toast.success(`${out.cards.length} cards criados: ${out.topic_title}`);
        openCards({ title: `Cards novos · ${out.topic_title}`, cards: out.cards });
      } else toast.info("Nenhum card novo: o modelo repetiu cards que você já tem.");
      onChanged();
    } catch (err) {
      toast.error(agentErrorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          {/* "Módulo 3" sem nome próprio não repete o número em cima */}
          {module.name !== `Módulo ${module.number}` && (
            <p className="text-xs text-muted-foreground">Módulo {module.number}</p>
          )}
          <h3 className="text-sm font-semibold">{module.name}</h3>
        </div>
        <StatusBadge className={st.className} dotClassName={st.dot}>
          {st.label}
        </StatusBadge>
      </div>
      {!open ? (
        <Button variant="ghost" size="sm" aria-expanded={false} aria-controls={listId} onClick={() => setOpen(true)}>
          Ver aulas ({module.lessons.length})
        </Button>
      ) : (
        <div id={listId} className="space-y-3">
          {module.lessons.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nenhuma aula ainda. Adicione as aulas do módulo abaixo.</p>
          ) : (
            <ul className="divide-y divide-border">
              {module.lessons.map((l) => (
                <li key={l.id} className="space-y-1 py-2">
                  <CheckboxRow
                    id={`lesson-${l.id}`}
                    checked={l.done}
                    onCheckedChange={(on) => void toggleLesson(l, on)}
                    trailing={
                      l.last_score !== null ? (
                        <span
                          className={cn(
                            "text-xs tabular-nums",
                            l.last_score >= 0.7 ? "text-success-text" : "text-muted-foreground",
                          )}
                        >
                          {pct(l.last_score)}
                        </span>
                      ) : undefined
                    }
                  >
                    <span className={cn(l.done && "text-muted-foreground")}>{l.title}</span>
                  </CheckboxRow>
                  {/* Ações da aula embaixo do título: o título não fica espremido em telas estreitas */}
                  <div className="flex flex-wrap gap-1 pl-8">
                    <Button variant="ghost" size="sm" onClick={() => onEditText(l)}>
                      <FileText aria-hidden="true" />
                      {l.has_text ? "Texto" : "Colar texto"}
                      <span className="sr-only"> de {l.title}</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={!l.has_text || pending !== null}
                      onClick={() =>
                        startSet({
                          userText: `Gerar questões da aula ${l.title}.`,
                          pendingLabel: "Gerando questões…",
                          path: "/agent/question-sets",
                          body: { topic_id: l.id, n_options: nOptions },
                        })
                      }
                    >
                      <Sparkles aria-hidden="true" />
                      Questões<span className="sr-only"> de {l.title}</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => void startDue(openCards, l.id, `Cards · ${l.title}`, "cursos")}
                    >
                      <Layers aria-hidden="true" />
                      Cards<span className="sr-only"> de {l.title}</span>
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <form onSubmit={addLesson} className="flex items-end gap-2">
            <div className="min-w-0 flex-1">
              <Field id={`new-lesson-${module.id}`} label="Nova aula">
                {() => (
                  <Input
                    id={`new-lesson-${module.id}`}
                    value={newLesson}
                    onChange={(e) => setNewLesson(e.target.value)}
                  />
                )}
              </Field>
            </div>
            <Button type="submit" variant="outline" disabled={!newLesson.trim()}>
              <Plus aria-hidden="true" />
              Adicionar
            </Button>
          </form>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" disabled={busy !== null} onClick={generateCards}>
              <Layers aria-hidden="true" />
              Gerar cards do módulo
            </Button>
            <Button variant="ghost" size="sm" onClick={toggleModule}>
              {module.status === "passed" ? "Reabrir módulo" : "Marcar módulo como concluído"}
            </Button>
          </div>
          {busy && (
            <p role="status" className="text-sm text-muted-foreground">
              {busy}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

/** v1.8 (D39, D41–D44): página de um curso — módulos, aulas, desempenho, certificado e cronômetro */
export function CourseDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { learningVersion } = useAgent();
  const course = useApi<Course>(`/courses/${id}`);
  const settings = useApi<SettingsResponse>("/settings");
  const [editing, setEditing] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [textFor, setTextFor] = React.useState<CourseLesson | null>(null);
  const [newModule, setNewModule] = React.useState("");
  const reload = course.reload;
  React.useEffect(() => {
    if (learningVersion > 0) void reload();
  }, [learningVersion, reload]);

  if (course.error)
    return (
      <div className="space-y-3">
        <p role="alert" className="text-sm text-destructive-text">
          Curso não encontrado.
        </p>
        <Link to="/cursos" className={buttonVariants({ variant: "outline", size: "sm" })}>
          Voltar para Meus cursos
        </Link>
      </div>
    );
  const c = course.data;
  if (!c) return <p className="text-sm text-muted-foreground">Carregando…</p>;

  const values = settings.data?.values ?? {};
  const nOptions = Number(values.options_per_question ?? 5) || 5;
  const canLaunchAcc = c.counts_acc && c.course_status === "done" && !c.acc_activity_id;

  const launchAcc = async () => {
    try {
      const out = await api.post<{ title: string; hours: number }>(`/courses/${c.id}/acc`, {});
      toast.success(`AAC lançada: ${out.title} (${out.hours}h)`);
      void reload();
    } catch (err) {
      toast.error(
        err instanceof Error && !err.message.startsWith("[") ? err.message : "Não foi possível lançar a AAC.",
      );
    }
  };
  const addModule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newModule.trim()) return;
    try {
      await api.post(`/courses/${c.id}/modules`, { name: newModule.trim() });
      setNewModule("");
      void reload();
    } catch {
      toast.error("Não foi possível adicionar o módulo.");
    }
  };

  const facts = [
    c.start_date && `Começou em ${formatDayMonth(parseLocalDate(c.start_date))}`,
    c.target_date &&
      `meta ${formatDayMonth(parseLocalDate(c.target_date))}${c.days_to_target !== null && c.days_to_target >= 0 ? ` (em ${c.days_to_target} dias)` : ""}`,
    c.modules_total > 0 && `${c.modules_done} de ${c.modules_total} módulos`,
    c.total_hours ? `${formatDuration(c.seconds)} de ${c.total_hours}h` : `${formatDuration(c.seconds)} estudadas`,
  ].filter(Boolean);

  return (
    <div className="space-y-6">
      <nav aria-label="Caminho" className="text-sm text-muted-foreground">
        <Link to="/cursos" className={cn("rounded-sm hover:text-foreground hover:underline", focusRing)}>
          Meus cursos
        </Link>
        <span aria-hidden="true"> › </span>
        <span className="text-foreground" aria-current="page">
          {c.name}
        </span>
      </nav>

      <header className="space-y-3">
        <div>
          <p className="text-xs text-muted-foreground">
            {[c.platform, c.type_label, c.counts_acc && "conta como AAC", c.status_label].filter(Boolean).join(" · ")}
          </p>
          <h1 className="text-2xl font-semibold">{c.name}</h1>
          <p className="text-sm text-muted-foreground">{facts.join(" · ")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {c.url && (
            <a
              href={c.url}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <ExternalLink aria-hidden="true" />
              Abrir {c.platform ? `no ${c.platform}` : "o curso"}
              <span className="sr-only"> (abre em outra aba)</span>
            </a>
          )}
          {c.notion_url && (
            <a
              href={c.notion_url}
              target="_blank"
              rel="noopener noreferrer"
              className={buttonVariants({ variant: "ghost", size: "sm" })}
            >
              <ExternalLink aria-hidden="true" />
              Página no Notion<span className="sr-only"> (abre em outra aba)</span>
            </a>
          )}
          <Button variant="ghost" size="sm" onClick={() => setEditing(true)}>
            <Pencil aria-hidden="true" />
            Editar curso
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setDeleting(true)}>
            <Trash2 aria-hidden="true" />
            Excluir curso
          </Button>
        </div>
      </header>

      {/* Resumo em linha; o cronômetro e os módulos em largura cheia (no meio estreito, ao lado do agente, o
          cronômetro não cabe numa coluna de 320px) */}
      <section aria-label="Resumo do curso" className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="space-y-1">
            <CardEyebrow>Desempenho no curso</CardEyebrow>
            <p className="text-2xl font-semibold tabular-nums">{pct(c.average_score)}</p>
            <p className="text-xs text-muted-foreground">
              acerto médio em {c.sets} teste(s) · {c.cards} card(s) · {formatDuration(c.seconds)} no cronômetro
            </p>
          </CardContent>
        </Card>
        {c.course_type === "certification" && (
          <Card>
            <CardContent className="space-y-1">
              <CardEyebrow>Prova de certificação</CardEyebrow>
              <p className="text-sm">
                {c.exam_at
                  ? `${formatDayMonth(parseLocalDateTime(c.exam_at))}${c.days_to_exam !== null && c.days_to_exam >= 0 ? ` · em ${c.days_to_exam} dias` : ""}`
                  : "Sem data marcada. Informe em Editar curso."}
              </p>
            </CardContent>
          </Card>
        )}
        <Card>
          <CardContent className="space-y-3">
            <CardEyebrow>Certificado</CardEyebrow>
            <p className="flex items-start gap-2 text-sm">
              <Award className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span>
                {c.course_status === "done"
                  ? c.certificate_path
                    ? `Certificado: ${c.certificate_path}`
                    : "Curso concluído. Guarde o certificado na pasta de materiais e informe o caminho em Editar curso."
                  : c.modules_total
                    ? `Sai ao concluir os ${c.modules_total} módulos.`
                    : "Sai ao concluir o curso."}
              </span>
            </p>
            {c.counts_acc &&
              (c.acc_activity_id ? (
                <p className="text-sm text-success-text">Lançado como AAC.</p>
              ) : (
                <>
                  <p className="text-xs text-muted-foreground">
                    Ao concluir: lançar como AAC{c.total_hours ? ` (${c.total_hours}h` : ""}
                    {c.total_hours && c.acc_category ? `, categoria ${c.acc_category})` : c.total_hours ? ")" : ""}.
                  </p>
                  <Button variant="outline" size="sm" disabled={!canLaunchAcc} onClick={launchAcc}>
                    <Award aria-hidden="true" />
                    Lançar como AAC
                  </Button>
                </>
              ))}
          </CardContent>
        </Card>
      </section>

      <TimerCard
        subjects={[]}
        goalMinutes={Number(values.timer_goal_minutes ?? 90)}
        alarmMinutes={Number(values.timer_alarm_minutes ?? 120)}
        onSaved={() => void reload()}
      />

      <section aria-labelledby="h-modules" className="space-y-3">
        <h2 id="h-modules" className="text-lg font-semibold">
          Módulos
        </h2>
        {c.modules_total === 0 && (
          <Card className="p-6">
            <p className="text-sm text-muted-foreground">
              Curso sem módulos: o progresso é o que você informa em Editar curso ({c.progress}%). Adicione módulos para
              marcar aulas e gerar questões.
            </p>
          </Card>
        )}
        {(c.modules ?? []).map((m) => (
          <ModuleCard
            key={m.id}
            module={m}
            nOptions={nOptions}
            onChanged={() => void reload()}
            onEditText={setTextFor}
          />
        ))}
        <form onSubmit={addModule} className="flex items-end gap-2">
          <div className="min-w-0 flex-1">
            <Field id="new-module" label="Novo módulo">
              {() => <Input id="new-module" value={newModule} onChange={(e) => setNewModule(e.target.value)} />}
            </Field>
          </div>
          <Button type="submit" variant="outline" disabled={!newModule.trim()}>
            <Plus aria-hidden="true" />
            Adicionar módulo
          </Button>
        </form>
      </section>

      <LessonTextDialog lesson={textFor} onClose={() => setTextFor(null)} onSaved={() => void reload()} />
      <CourseDialog open={editing} course={c} onOpenChange={setEditing} onSaved={() => void reload()} />
      <ConfirmDialog
        open={deleting}
        onOpenChange={setDeleting}
        title="Excluir este curso?"
        note={`"${c.name}" sai de Meus cursos com os módulos, as aulas, os testes e os cards dele. A AAC já lançada continua. Não dá para desfazer.`}
        confirmLabel="Excluir curso"
        destructive
        onConfirm={async () => {
          await api.del(`/courses/${c.id}`);
          toast.success("Curso excluído");
          navigate("/cursos");
        }}
      />
    </div>
  );
}
