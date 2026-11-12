import { ListChecks, Pencil, Plus } from "lucide-react";
import * as React from "react";

import { RecordList } from "@/components/manage/RecordList";
import { STATUS_LABEL, SubjectDialog } from "@/components/manage/SubjectDialog";
import { TopicsDialog } from "@/components/manage/TopicsDialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import type { Degree, Semester, Subject } from "@/lib/api";
import { useApi } from "@/lib/useApi";

/** Gerenciar › Disciplinas e temas */
export function SubjectsPage() {
  const degrees = useApi<Degree[]>("/degrees");
  const semesters = useApi<Semester[]>("/semesters");
  const subjects = useApi<Subject[]>("/subjects");
  const presets = useApi<Record<string, { label: string }>>("/grading-rules/presets");

  const current = semesters.data?.find((s) => s.is_current);
  const [filter, setFilter] = React.useState<string>("current");
  const [editing, setEditing] = React.useState<Subject | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [topicsOf, setTopicsOf] = React.useState<Subject | null>(null);

  const rows = (subjects.data ?? []).filter((s) => {
    if (filter === "current") return current ? s.semester_id === current.id : false;
    if (filter === "pending") return s.semester_id === null;
    if (filter === "all") return true;
    return s.semester_id === Number(filter);
  });

  const semesterCode = (id: number | null) => semesters.data?.find((s) => s.id === id)?.code ?? "—";
  const degreeId = degrees.data?.[0]?.id;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Disciplinas e temas</h1>
          <p className="text-sm text-muted-foreground">Cadastro, regra de avaliação, progresso do portal e temas.</p>
        </div>
        <Button onClick={() => setCreating(true)} disabled={!degreeId}>
          <Plus aria-hidden="true" />
          Nova disciplina
        </Button>
      </header>

      <div className="flex flex-col gap-2 sm:w-auto">
        <Label htmlFor="filter-semester">Mostrar</Label>
        <Select
          id="filter-semester"
          className="min-w-[180px] max-w-[280px] sm:w-auto"
          value={filter}
          onValueChange={setFilter}
          options={[
            { value: "current", label: current ? `Semestre atual (${current.code})` : "Semestre atual" },
            { value: "pending", label: "Pendentes (sem semestre)" },
            ...(semesters.data ?? []).filter((s) => !s.is_current).map((s) => ({ value: String(s.id), label: s.code })),
            { value: "all", label: "Todas" },
          ]}
        />
      </div>

      {subjects.error ? (
        <p role="alert" className="text-sm text-destructive-text">
          Não foi possível carregar as disciplinas: {subjects.error}
        </p>
      ) : (
        <RecordList
          caption="Disciplinas"
          rows={rows}
          rowKey={(s) => s.id}
          title={(s) => s.name}
          empty="Nenhuma disciplina neste filtro."
          columns={[
            { header: "Semestre", cell: (s) => semesterCode(s.semester_id), inCard: true },
            { header: "Situação", cell: (s) => STATUS_LABEL[s.status], inCard: true },
            { header: "Carga", cell: (s) => (s.hours ? `${s.hours}h` : "—"), numeric: true, inCard: true },
          ]}
          actions={(s) => (
            <>
              <Button variant="outline" size="sm" onClick={() => setTopicsOf(s)}>
                <ListChecks aria-hidden="true" />
                Temas
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setEditing(s)}>
                <Pencil aria-hidden="true" />
                Editar
              </Button>
            </>
          )}
        />
      )}

      {degreeId && (
        <SubjectDialog
          open={creating || editing !== null}
          onOpenChange={(o) => {
            if (!o) {
              setCreating(false);
              setEditing(null);
            }
          }}
          subject={editing}
          degreeId={degreeId}
          semesters={semesters.data ?? []}
          presets={presets.data ?? {}}
          onSaved={subjects.reload}
        />
      )}
      <TopicsDialog subject={topicsOf} onOpenChange={(o) => !o && setTopicsOf(null)} onSaved={subjects.reload} />
    </div>
  );
}
