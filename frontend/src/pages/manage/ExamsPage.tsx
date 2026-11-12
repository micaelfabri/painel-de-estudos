import { Pencil, Plus } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { RecordList } from "@/components/manage/RecordList";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, type Deadline, type Exam, type Subject } from "@/lib/api";
import { formatDayMonth, formatTime, parseLocalDate, parseLocalDateTime } from "@/lib/format";
import { useApi } from "@/lib/useApi";

type Editing = { type: "exam"; item: Exam | null } | { type: "deadline"; item: Deadline | null } | null;

function examWhen(e: Exam) {
  if (e.scheduled_at) {
    const d = parseLocalDateTime(e.scheduled_at);
    return `${formatDayMonth(d)} ${formatTime(d)}`;
  }
  return e.schedule_by ? `Agendar até ${formatDayMonth(parseLocalDate(e.schedule_by))}` : "—";
}

/** Gerenciar › Provas e prazos */
export function ExamsPage() {
  const exams = useApi<Exam[]>("/exams");
  const deadlines = useApi<Deadline[]>("/deadlines");
  const subjects = useApi<Subject[]>("/subjects");
  const [editing, setEditing] = React.useState<Editing>(null);
  const subjectName = (id: number | null) => subjects.data?.find((s) => s.id === id)?.name ?? "—";

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Provas e prazos</h1>
          <p className="text-sm text-muted-foreground">Aparecem na próxima prova, nos cards e na faixa de 14 dias.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEditing({ type: "deadline", item: null })}>
            <Plus aria-hidden="true" />
            Novo prazo ou evento
          </Button>
          <Button onClick={() => setEditing({ type: "exam", item: null })}>
            <Plus aria-hidden="true" />
            Nova prova
          </Button>
        </div>
      </header>

      <section className="space-y-3" aria-labelledby="h-provas">
        <h2 id="h-provas" className="text-lg font-semibold">
          Provas
        </h2>
        <RecordList
          caption="Provas"
          rows={exams.data ?? []}
          rowKey={(e) => e.id}
          title={(e) => subjectName(e.subject_id)}
          empty="Nenhuma prova cadastrada."
          columns={[
            { header: "Tipo", cell: (e) => e.kind, inCard: true },
            { header: "Quando", cell: examWhen, inCard: true },
            { header: "Local", cell: (e) => e.location ?? "—", inCard: true },
          ]}
          actions={(e) => (
            <Button variant="ghost" size="sm" onClick={() => setEditing({ type: "exam", item: e })}>
              <Pencil aria-hidden="true" />
              Editar
            </Button>
          )}
        />
      </section>

      <section className="space-y-3" aria-labelledby="h-prazos">
        <h2 id="h-prazos" className="text-lg font-semibold">
          Prazos e eventos
        </h2>
        <RecordList
          caption="Prazos e eventos"
          rows={deadlines.data ?? []}
          rowKey={(d) => d.id}
          title={(d) => d.title}
          empty="Nenhum prazo ou evento cadastrado."
          columns={[
            { header: "Tipo", cell: (d) => (d.kind === "event" ? "Evento" : "Prazo"), inCard: true },
            { header: "Data", cell: (d) => formatDayMonth(parseLocalDate(d.due_date)), inCard: true },
            { header: "Disciplina", cell: (d) => subjectName(d.subject_id), inCard: true },
          ]}
          actions={(d) => (
            <Button variant="ghost" size="sm" onClick={() => setEditing({ type: "deadline", item: d })}>
              <Pencil aria-hidden="true" />
              Editar
            </Button>
          )}
        />
      </section>

      <EditDialog
        editing={editing}
        subjects={subjects.data ?? []}
        onClose={() => setEditing(null)}
        onSaved={() => {
          void exams.reload();
          void deadlines.reload();
        }}
      />
    </div>
  );
}

function EditDialog({
  editing,
  subjects,
  onClose,
  onSaved,
}: {
  editing: Editing;
  subjects: Subject[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [v, setV] = React.useState<Record<string, string>>({});
  const [error, setError] = React.useState<string>();

  React.useEffect(() => {
    setError(undefined);
    if (!editing) return;
    if (editing.type === "exam") {
      const e = editing.item;
      setV({
        subject: e ? String(e.subject_id) : "",
        kind: e?.kind ?? "AV",
        date: e?.scheduled_at?.slice(0, 10) ?? "",
        time: e?.scheduled_at?.slice(11, 16) ?? "",
        schedule_by: e?.schedule_by ?? "",
        location: e?.location ?? "",
      });
    } else {
      const d = editing.item;
      setV({
        subject: d?.subject_id ? String(d.subject_id) : "none",
        title: d?.title ?? "",
        date: d?.due_date ?? "",
        kind: d?.kind ?? "deadline",
      });
    }
  }, [editing]);

  const set = (k: string) => (value: string) => setV((x) => ({ ...x, [k]: value }));

  const save = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!editing) return;
    try {
      if (editing.type === "exam") {
        if (!v.subject) return setError("Escolha a disciplina.");
        if (!v.date && !v.schedule_by) return setError("Informe a data da prova ou o limite para agendar.");
        const body = {
          ...(editing.item ?? {}),
          subject_id: Number(v.subject),
          kind: v.kind || "AV",
          scheduled_at: v.date ? `${v.date}T${v.time || "00:00"}:00` : null,
          schedule_by: v.schedule_by || null,
          location: v.location || null,
        };
        if (editing.item) await api.put(`/exams/${editing.item.id}`, body);
        else await api.post("/exams", body);
      } else {
        if (!v.title?.trim() || !v.date) return setError("Informe o título e a data.");
        const body = {
          ...(editing.item ?? {}),
          subject_id: v.subject === "none" ? null : Number(v.subject),
          title: v.title.trim(),
          due_date: v.date,
          kind: v.kind,
        };
        if (editing.item) await api.put(`/deadlines/${editing.item.id}`, body);
        else await api.post("/deadlines", body);
      }
      toast.success("Salvo");
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar");
    }
  };

  const subjectOptions = subjects.map((s) => ({ value: String(s.id), label: s.name }));
  const isExam = editing?.type === "exam";

  return (
    <Dialog open={editing !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        title={
          isExam
            ? editing?.item
              ? "Editar prova"
              : "Nova prova"
            : editing?.item
              ? "Editar prazo ou evento"
              : "Novo prazo ou evento"
        }
      >
        <form onSubmit={save} className="grid grid-cols-1 gap-4" noValidate>
          {isExam ? (
            <>
              <Field id="e-subject" label="Disciplina">
                {() => (
                  <Select
                    id="e-subject"
                    value={v.subject ?? ""}
                    onValueChange={set("subject")}
                    placeholder="Escolha"
                    options={subjectOptions}
                  />
                )}
              </Field>
              <Field id="e-kind" label="Tipo">
                {() => <Input id="e-kind" value={v.kind ?? ""} onChange={(e) => set("kind")(e.target.value)} />}
              </Field>
              <Field id="e-date" label="Data" optional>
                {() => <Input id="e-date" type="date" value={v.date ?? ""} onChange={(e) => set("date")(e.target.value)} />}
              </Field>
              <Field id="e-time" label="Hora" optional>
                {() => <Input id="e-time" type="time" value={v.time ?? ""} onChange={(e) => set("time")(e.target.value)} />}
              </Field>
              <Field id="e-by" label="Agendar até" optional hint="Use quando a prova ainda não tem data marcada.">
                {(d) => (
                  <Input
                    id="e-by"
                    type="date"
                    aria-describedby={d}
                    value={v.schedule_by ?? ""}
                    onChange={(e) => set("schedule_by")(e.target.value)}
                  />
                )}
              </Field>
              <Field id="e-loc" label="Local" optional>
                {() => <Input id="e-loc" value={v.location ?? ""} onChange={(e) => set("location")(e.target.value)} />}
              </Field>
            </>
          ) : (
            <>
              <Field id="d-title" label="Título">
                {() => <Input id="d-title" value={v.title ?? ""} onChange={(e) => set("title")(e.target.value)} />}
              </Field>
              <Field id="d-date" label="Data">
                {() => <Input id="d-date" type="date" value={v.date ?? ""} onChange={(e) => set("date")(e.target.value)} />}
              </Field>
              <Field id="d-kind" label="Tipo">
                {() => (
                  <Select
                    id="d-kind"
                    value={v.kind ?? "deadline"}
                    onValueChange={set("kind")}
                    options={[
                      { value: "deadline", label: "Prazo" },
                      { value: "event", label: "Evento" },
                    ]}
                  />
                )}
              </Field>
              <Field id="d-subject" label="Disciplina" optional>
                {() => (
                  <Select
                    id="d-subject"
                    value={v.subject ?? "none"}
                    onValueChange={set("subject")}
                    options={[{ value: "none", label: "Nenhuma" }, ...subjectOptions]}
                  />
                )}
              </Field>
            </>
          )}
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
        </form>
      </DialogContent>
    </Dialog>
  );
}
