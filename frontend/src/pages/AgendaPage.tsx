import { ClipboardCheck, Pencil, Plus } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { ResultDialog } from "@/components/study/ResultDialog";
import { CategoryBadge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { api, type AgendaItem, type Deadline, type Exam, type Subject } from "@/lib/api";
import { formatDayMonth, parseLocalDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { cn } from "@/lib/utils";
import { EditDialog, type Editing } from "@/pages/manage/ExamsPage";

const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** Estudo › Provas e prazos (SPEC D14): tudo numa lista, com marcar como feito, editar e lançar resultado */
export function AgendaPage() {
  const agenda = useApi<AgendaItem[]>("/study/agenda");
  const subjects = useApi<Subject[]>("/subjects");
  const [editing, setEditing] = React.useState<Editing>(null);
  const [resultFor, setResultFor] = React.useState<AgendaItem | null>(null);
  // v1.5: marcar/desmarcar como feito pede confirmação (evita marcar a prova errada sem querer)
  const [confirming, setConfirming] = React.useState<{ item: AgendaItem; value: boolean } | null>(null);
  const today = todayIso();

  const items = agenda.data ?? [];
  const open = items.filter((i) => !i.done && (i.date === null || i.date >= today));
  const late = items.filter((i) => !i.done && i.date !== null && i.date < today);
  const done = items.filter((i) => i.done);

  const toggle = async (item: AgendaItem, value: boolean) => {
    // Erro sobe para o diálogo de confirmação, que fica aberto com "Nada foi alterado."
    await api.patch(`/study/${item.type === "exam" ? "exams" : "deadlines"}/${item.id}/done`, { done: value });
    agenda.setData((list) =>
      (list ?? []).map((i) => (i.id === item.id && i.type === item.type ? { ...i, done: value } : i)),
    );
    toast.success(value ? "Marcado como feito" : "Voltou para pendente");
  };

  const edit = async (item: AgendaItem) => {
    try {
      if (item.type === "exam")
        setEditing({
          type: "exam",
          item: await api.get<Exam>(`/exams/${item.id}`),
        });
      else
        setEditing({
          type: "deadline",
          item: await api.get<Deadline>(`/deadlines/${item.id}`),
        });
    } catch {
      toast.error("Não foi possível abrir para editar.");
    }
  };

  const section = (id: string, title: string, rows: AgendaItem[], empty: string) => (
    <section className="space-y-3" aria-labelledby={id}>
      <h2 id={id} className="text-lg font-semibold">
        {title} <span className="text-sm font-normal text-muted-foreground">({rows.length})</span>
      </h2>
      {rows.length === 0 ? (
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">{empty}</p>
        </Card>
      ) : (
        <Card>
          <ul className="divide-y divide-border">
            {rows.map((item) => (
              <AgendaRow
                key={`${item.type}-${item.id}`}
                item={item}
                onToggle={(v) => setConfirming({ item, value: v })}
                onEdit={() => edit(item)}
                onResult={() => setResultFor(item)}
              />
            ))}
          </ul>
        </Card>
      )}
    </section>
  );

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Provas e prazos</h1>
          <p className="text-sm text-muted-foreground">
            Provas, prazos, laboratórios e atividades. Marque o que já fez e lance o resultado.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setEditing({ type: "deadline", item: null })}>
            <Plus aria-hidden="true" />
            Prazo, lab ou atividade
          </Button>
          <Button onClick={() => setEditing({ type: "exam", item: null })}>
            <Plus aria-hidden="true" />
            Nova prova
          </Button>
        </div>
      </header>

      {agenda.error && (
        <p role="alert" className="text-sm text-destructive-text">
          {agenda.error}
        </p>
      )}
      {late.length > 0 && section("h-late", "Atrasados", late, "")}
      {section("h-open", "Próximos", open, "Nada pendente por aqui.")}
      {section("h-done", "Feitos", done, "Nada marcado como feito ainda.")}

      <EditDialog
        editing={editing}
        subjects={subjects.data ?? []}
        onClose={() => setEditing(null)}
        onSaved={() => void agenda.reload()}
      />
      <ConfirmDialog
        open={confirming !== null}
        onOpenChange={(v) => !v && setConfirming(null)}
        title={
          confirming?.value
            ? `Marcar "${confirming.item.title}" como feito?`
            : `Desmarcar "${confirming?.item.title ?? ""}"?`
        }
        note={
          confirming?.value
            ? "Vai para Feitos. Dá para desmarcar depois."
            : "Volta para Próximos (ou Atrasados, se a data já passou). A nota lançada continua salva."
        }
        confirmLabel={confirming?.value ? "Marcar como feito" : "Desmarcar"}
        onConfirm={() => (confirming ? toggle(confirming.item, confirming.value) : undefined)}
      />
      <ResultDialog
        item={resultFor}
        onClose={() => setResultFor(null)}
        onSaved={() => {
          setResultFor(null);
          void agenda.reload();
        }}
      />
    </div>
  );
}

function AgendaRow({
  item,
  onToggle,
  onEdit,
  onResult,
}: {
  item: AgendaItem;
  onToggle: (v: boolean) => void;
  onEdit: () => void;
  onResult: () => void;
}) {
  const id = `ag-${item.type}-${item.id}`;
  const when = item.date ? formatDayMonth(parseLocalDate(item.date)) : "Sem data";
  const canScore = item.type === "exam" || ["lab", "activity", "mock"].includes(item.kind);
  return (
    <li className="flex items-start gap-3 px-4 py-3 md:items-center">
      <Checkbox
        className="mt-1 md:mt-0"
        id={id}
        checked={item.done}
        onCheckedChange={(v) => onToggle(v === true)}
        aria-label={`${item.done ? "Desmarcar" : "Marcar como feito"}: ${item.title}`}
      />
      <div className="flex min-w-0 flex-1 flex-col gap-2 md:flex-row md:items-center md:gap-3">
        <div className="min-w-0 flex-1">
          <label
            htmlFor={id}
            className={cn(
              "block cursor-pointer text-sm font-medium",
              item.done && "text-muted-foreground line-through",
            )}
          >
            {item.title}
          </label>
          <p className="text-xs text-muted-foreground">
            {item.to_schedule ? `Agendar até ${when}` : when}
            {item.time && ` · ${item.time}`}
            {item.subject_name && item.type !== "exam" && ` · ${item.subject_name}`}
            {item.location && ` · ${item.location}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <CategoryBadge className="bg-muted text-foreground">{item.kind_label}</CategoryBadge>
          {item.score !== null && (
            <span className="text-sm font-semibold tabular-nums" title="Nota">
              {item.score.toLocaleString("pt-BR")}
              {item.wrong_attempts ? (
                <span className="ml-1 text-xs font-normal text-muted-foreground">· {item.wrong_attempts} erro(s)</span>
              ) : null}
            </span>
          )}
          <div className="flex gap-1">
            {canScore && (
              <Button variant="ghost" size="sm" onClick={onResult}>
                <ClipboardCheck aria-hidden="true" />
                Resultado
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={onEdit}>
              <Pencil aria-hidden="true" />
              Editar
            </Button>
          </div>
        </div>
      </div>
    </li>
  );
}
