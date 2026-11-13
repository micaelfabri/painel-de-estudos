import { Info, Pencil, Plus, Trash2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { RecordList } from "@/components/manage/RecordList";
import { InlineMeter } from "@/components/panel/InlineMeter";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardEyebrow } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, type AccActivity, type CourseProgress } from "@/lib/api";
import { formatDayMonth, formatNumber, parseLocalDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";

/** Gerenciar › Atividades complementares (ACC/AAC) contra o total exigido (SPEC §6.5) */
export function AccPage() {
  const progress = useApi<CourseProgress>("/course/progress");
  const activities = useApi<AccActivity[]>("/acc-activities");
  const [editing, setEditing] = React.useState<AccActivity | "new" | null>(null);
  const listRef = React.useRef<HTMLDivElement>(null);
  const acc = progress.data?.acc;
  const degreeId = progress.data?.degree.id;

  const reload = () => {
    void progress.reload();
    void activities.reload();
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Atividades complementares</h1>
          <p className="text-sm text-muted-foreground">
            Horas de ACC (AAC no histórico) contra o total exigido pelo curso.
          </p>
        </div>
        <Button onClick={() => setEditing("new")} disabled={!degreeId}>
          <Plus aria-hidden="true" />
          Nova atividade
        </Button>
      </header>

      {acc && (
        <section aria-label="Resumo" className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardContent className="space-y-3">
              <CardEyebrow>Horas lançadas</CardEyebrow>
              <p className="text-2xl font-semibold tabular-nums">
                {formatNumber(acc.counted_hours, 1)}h
                {acc.required_hours !== null && (
                  <span className="text-sm font-normal text-muted-foreground">
                    {" "}
                    de {formatNumber(acc.required_hours)}h
                  </span>
                )}
              </p>
              {acc.required_hours ? (
                <InlineMeter
                  label="ACC lançadas"
                  hideLabel
                  value={Math.min(100, (acc.counted_hours / acc.required_hours) * 100)}
                />
              ) : null}
              <p className="text-xs text-muted-foreground">
                {acc.missing_hours !== null && `Faltam ${formatNumber(acc.missing_hours, 1)}h`}
                {acc.planned_hours > 0 && ` · ${formatNumber(acc.planned_hours, 1)}h planejadas, ainda não lançadas`}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="space-y-3">
              <CardEyebrow>Por categoria</CardEyebrow>
              <ul className="space-y-2">
                {acc.categories.map((c) => (
                  <li key={c.category} className="flex justify-between gap-2 text-sm">
                    <span>{c.category}</span>
                    <span className="tabular-nums text-muted-foreground">
                      {formatNumber(c.counted, 1)}h{c.cap !== null && ` de ${c.cap}h no máximo`}
                      {c.counted < c.registered && ` (${formatNumber(c.registered, 1)}h lançadas)`}
                    </span>
                  </li>
                ))}
              </ul>
              {!acc.rules_known && (
                <p className="flex items-start gap-2 text-xs text-muted-foreground">
                  <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  Categorias aceitas, limites e prazo ainda não são conhecidos: falta o regulamento de AAC do curso.
                </p>
              )}
            </CardContent>
          </Card>
        </section>
      )}

      {/* Resposta 06 do DS: depois de excluir, o foco volta para a lista */}
      <div ref={listRef} tabIndex={-1} aria-label="Lista de atividades" className="focus:outline-none">
        <RecordList
          caption="Atividades complementares"
          rows={activities.data ?? []}
          rowKey={(a) => a.id}
          title={(a) => a.title}
          empty="Nenhuma atividade cadastrada."
          columns={[
            { header: "Categoria", cell: (a) => a.category ?? "—", inCard: true },
            {
              header: "Data",
              cell: (a) =>
                a.activity_date
                  ? formatDayMonth(parseLocalDate(a.activity_date)) + "/" + a.activity_date.slice(0, 4)
                  : "—",
              inCard: true,
            },
            { header: "Horas", cell: (a) => `${formatNumber(a.hours, 1)}h`, numeric: true, inCard: true },
            { header: "Situação", cell: (a) => (a.status === "registered" ? "Lançada" : "Planejada") },
          ]}
          actions={(a) => (
            <Button variant="ghost" size="sm" onClick={() => setEditing(a)}>
              <Pencil aria-hidden="true" />
              Editar
            </Button>
          )}
        />
      </div>

      {degreeId && (
        <AccDialog
          editing={editing}
          degreeId={degreeId}
          onClose={() => setEditing(null)}
          onSaved={reload}
          onDeleted={() => listRef.current?.focus()}
        />
      )}
    </div>
  );
}

function AccDialog({
  editing,
  degreeId,
  onClose,
  onSaved,
  onDeleted,
}: {
  editing: AccActivity | "new" | null;
  degreeId: number;
  onClose: () => void;
  onSaved: () => void;
  onDeleted?: () => void;
}) {
  const item = editing === "new" ? null : editing;
  const [v, setV] = React.useState({
    title: "",
    category: "",
    hours: "",
    date: "",
    path: "",
    status: "registered",
    notes: "",
  });
  const [error, setError] = React.useState<string>();
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const deleted = React.useRef(false);

  React.useEffect(() => {
    setError(undefined);
    setV({
      title: item?.title ?? "",
      category: item?.category ?? "",
      hours: item ? String(item.hours) : "",
      date: item?.activity_date ?? "",
      path: item?.certificate_path ?? "",
      status: item?.status ?? "registered",
      notes: item?.notes ?? "",
    });
  }, [editing, item]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const hours = Number(v.hours.replace(",", "."));
    if (!v.title.trim()) return setError("Informe a atividade.");
    if (!(hours > 0)) return setError("Informe as horas (maior que zero).");
    const body = {
      degree_id: degreeId,
      title: v.title.trim(),
      category: v.category.trim() || null,
      hours,
      activity_date: v.date || null,
      certificate_path: v.path.trim() || null,
      status: v.status,
      notes: v.notes.trim() || null,
    };
    try {
      if (item) await api.put(`/acc-activities/${item.id}`, body);
      else await api.post("/acc-activities", body);
      toast.success("Atividade salva");
      onSaved();
      onClose();
    } catch {
      setError("Não foi possível salvar.");
    }
  };

  // v1.7.2: excluir uma atividade lançada por engano (com confirmação)
  const remove = async () => {
    if (!item) return;
    await api.del(`/acc-activities/${item.id}`);
    deleted.current = true;
    toast.success("Atividade excluída");
    onSaved();
    onClose();
  };

  return (
    <Dialog open={editing !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={item ? "Editar atividade" : "Nova atividade"}
        onCloseAutoFocus={(e) => {
          if (!deleted.current) return;
          deleted.current = false;
          e.preventDefault();
          onDeleted?.();
        }}
      >
        <form onSubmit={save} className="grid grid-cols-1 gap-4" noValidate>
          <Field id="a-title" label="Atividade">
            {() => <Input id="a-title" value={v.title} onChange={(e) => setV({ ...v, title: e.target.value })} />}
          </Field>
          <Field
            id="a-cat"
            label="Categoria"
            optional
            hint="Use o nome da categoria do regulamento, quando ele chegar."
          >
            {(d) => (
              <Input
                id="a-cat"
                aria-describedby={d}
                value={v.category}
                onChange={(e) => setV({ ...v, category: e.target.value })}
              />
            )}
          </Field>
          <Field id="a-hours" label="Horas">
            {() => (
              <Input
                id="a-hours"
                inputMode="decimal"
                value={v.hours}
                onChange={(e) => setV({ ...v, hours: e.target.value })}
              />
            )}
          </Field>
          <Field id="a-date" label="Data" optional>
            {() => (
              <Input id="a-date" type="date" value={v.date} onChange={(e) => setV({ ...v, date: e.target.value })} />
            )}
          </Field>
          <Field id="a-path" label="Caminho do certificado" optional hint="Ex.: D:\Cursos\…\certificado.pdf">
            {(d) => (
              <Input
                id="a-path"
                aria-describedby={d}
                value={v.path}
                onChange={(e) => setV({ ...v, path: e.target.value })}
              />
            )}
          </Field>
          <Field id="a-status" label="Situação">
            {() => (
              <Select
                id="a-status"
                value={v.status}
                onValueChange={(s) => setV({ ...v, status: s })}
                options={[
                  { value: "registered", label: "Lançada no portal" },
                  { value: "planned", label: "Planejada (ainda não lançada)" },
                ]}
              />
            )}
          </Field>
          <Field id="a-notes" label="Observações" optional>
            {() => <Textarea id="a-notes" value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} />}
          </Field>
          {error && (
            <p role="alert" className="text-sm text-destructive-text">
              {error}
            </p>
          )}
          <div className="flex gap-3 pt-2">
            <Button variant="secondary" className="flex-1" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" className="flex-1">
              Salvar
            </Button>
          </div>
          {item && (
            <Button type="button" variant="ghost" className="justify-self-start" onClick={() => setConfirmDelete(true)}>
              <Trash2 aria-hidden="true" />
              Excluir atividade
            </Button>
          )}
        </form>
        <ConfirmDialog
          open={confirmDelete}
          onOpenChange={setConfirmDelete}
          title="Excluir esta atividade?"
          note={
            item
              ? `"${item.title}" (${formatNumber(item.hours)}h) sai da lista e das horas de ACC. Não dá para desfazer.`
              : undefined
          }
          confirmLabel="Excluir atividade"
          destructive
          onConfirm={remove}
        />
      </DialogContent>
    </Dialog>
  );
}
