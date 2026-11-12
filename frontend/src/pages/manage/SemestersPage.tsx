import { Pencil, Plus } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { CourseProgressCard } from "@/components/manage/CourseProgressCard";
import { RecordList } from "@/components/manage/RecordList";
import { Button } from "@/components/ui/button";
import { CheckboxRow } from "@/components/ui/checkbox";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { api, type CourseProgress, type Degree, type Semester } from "@/lib/api";
import { formatDayMonth, parseLocalDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";

/** Gerenciar › Semestres (o semestre atual alimenta o painel) */
export function SemestersPage() {
  const degrees = useApi<Degree[]>("/degrees");
  const semesters = useApi<Semester[]>("/semesters");
  const progress = useApi<CourseProgress>("/course/progress");
  const [editing, setEditing] = React.useState<Semester | null | "new">(null);
  const degree = degrees.data?.[0];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Semestres e curso</h1>
          <p className="text-sm text-muted-foreground">
            {degree ? `${degree.name} · ${degree.institution ?? ""}` : "Nenhuma graduação cadastrada"}
          </p>
        </div>
        <Button onClick={() => setEditing("new")} disabled={!degree}>
          <Plus aria-hidden="true" />
          Novo semestre
        </Button>
      </header>

      {progress.data && <CourseProgressCard data={progress.data} onSaved={progress.reload} />}

      <h2 className="text-lg font-semibold">Semestres</h2>
      <RecordList
        caption="Semestres"
        rows={semesters.data ?? []}
        rowKey={(s) => s.id}
        title={(s) => s.code}
        empty="Nenhum semestre cadastrado."
        columns={[
          { header: "Atual", cell: (s) => (s.is_current ? "Sim" : "Não"), inCard: true },
          { header: "Início", cell: (s) => (s.start_date ? formatDayMonth(parseLocalDate(s.start_date)) : "—"), inCard: true },
          { header: "Fim", cell: (s) => (s.end_date ? formatDayMonth(parseLocalDate(s.end_date)) : "—"), inCard: true },
        ]}
        actions={(s) => (
          <Button variant="ghost" size="sm" onClick={() => setEditing(s)}>
            <Pencil aria-hidden="true" />
            Editar
          </Button>
        )}
      />

      {progress.data && progress.data.unscheduled.length > 0 && (
        <section aria-labelledby="h-sem-semestre" className="space-y-3">
          <h2 id="h-sem-semestre" className="text-lg font-semibold">
            Disciplinas ainda sem semestre ({progress.data.unscheduled.length})
          </h2>
          <p className="text-sm text-muted-foreground">A divisão por semestre depende da matriz curricular (currículo 202202).</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {progress.data.unscheduled.map((s) => (
              <li key={s.id} className="flex justify-between gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm">
                <span>{s.name}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground">{s.hours ? `${s.hours}h` : "—"}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {degree && (
        <SemesterDialog
          editing={editing}
          degreeId={degree.id}
          others={semesters.data ?? []}
          onClose={() => setEditing(null)}
          onSaved={() => {
            void semesters.reload();
            void progress.reload();
          }}
        />
      )}
    </div>
  );
}

function SemesterDialog({
  editing,
  degreeId,
  others,
  onClose,
  onSaved,
}: {
  editing: Semester | null | "new";
  degreeId: number;
  others: Semester[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const item = editing === "new" ? null : editing;
  const [v, setV] = React.useState({ code: "", start: "", end: "", current: false });
  const [error, setError] = React.useState<string>();

  React.useEffect(() => {
    setError(undefined);
    setV({
      code: item?.code ?? "",
      start: item?.start_date ?? "",
      end: item?.end_date ?? "",
      current: item?.is_current ?? false,
    });
  }, [editing, item]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!v.code.trim()) return setError("Informe o código do semestre (ex.: 2027.1).");
    try {
      const body = {
        degree_id: degreeId,
        code: v.code.trim(),
        start_date: v.start || null,
        end_date: v.end || null,
        is_current: v.current,
        notes: item?.notes ?? null,
      };
      // Só um semestre atual por vez
      if (v.current) {
        for (const o of others.filter((o) => o.is_current && o.id !== item?.id)) {
          await api.put(`/semesters/${o.id}`, { ...o, is_current: false });
        }
      }
      if (item) await api.put(`/semesters/${item.id}`, body);
      else await api.post("/semesters", body);
      toast.success("Semestre salvo");
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar");
    }
  };

  return (
    <Dialog open={editing !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={item ? "Editar semestre" : "Novo semestre"}>
        <form onSubmit={save} className="grid grid-cols-1 gap-4" noValidate>
          <Field id="sem-code" label="Código" error={error}>
            {(d) => (
              <Input
                id="sem-code"
                value={v.code}
                aria-invalid={!!error}
                aria-describedby={d}
                onChange={(e) => setV({ ...v, code: e.target.value })}
              />
            )}
          </Field>
          <Field id="sem-start" label="Início" optional>
            {() => <Input id="sem-start" type="date" value={v.start} onChange={(e) => setV({ ...v, start: e.target.value })} />}
          </Field>
          <Field id="sem-end" label="Fim" optional>
            {() => <Input id="sem-end" type="date" value={v.end} onChange={(e) => setV({ ...v, end: e.target.value })} />}
          </Field>
          <CheckboxRow id="sem-current" checked={v.current} onCheckedChange={(c) => setV({ ...v, current: c })}>
            Semestre atual (aparece no painel)
          </CheckboxRow>
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
