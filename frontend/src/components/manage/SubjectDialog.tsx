import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { CheckboxRow } from "@/components/ui/checkbox";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { api, type PortalProgress, type Semester, type Subject } from "@/lib/api";

export const STATUS_LABEL: Record<Subject["status"], string> = {
  pending: "Pendente",
  in_progress: "Cursando",
  passed: "Aprovada",
  failed: "Reprovada",
};

const NUM_FIELDS: { key: keyof PortalProgress; label: string }[] = [
  { key: "contents_done", label: "Conteúdos feitos" },
  { key: "contents_total", label: "Conteúdos no total" },
  { key: "exercises_done", label: "Exercícios feitos" },
  { key: "exercises_total", label: "Exercícios no total" },
  { key: "mocks_done", label: "Simulados feitos" },
  { key: "mocks_total", label: "Simulados no total" },
  { key: "lab_done", label: "Laboratório feito" },
  { key: "lab_total", label: "Laboratório no total" },
];

const toNum = (v: string) => (v.trim() === "" ? null : Number(v.replace(",", ".")));

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subject: Subject | null;
  degreeId: number;
  semesters: Semester[];
  presets: Record<string, { label: string }>;
  onSaved: () => void;
}

/** Cadastro de disciplina + progresso do portal (modo Gerenciar) */
export function SubjectDialog({ open, onOpenChange, subject, degreeId, semesters, presets, onSaved }: Props) {
  const [form, setForm] = React.useState({
    name: "",
    code: "",
    hours: "",
    semester: "none",
    status: "pending" as Subject["status"],
    preset: "keep",
    lab: false,
  });
  const [progress, setProgress] = React.useState<Record<string, string>>({});
  const [error, setError] = React.useState<string | undefined>();

  React.useEffect(() => {
    if (!open) return;
    setError(undefined);
    setForm({
      name: subject?.name ?? "",
      code: subject?.code ?? "",
      hours: subject?.hours?.toString() ?? "",
      semester: subject?.semester_id ? String(subject.semester_id) : "none",
      status: subject?.status ?? "pending",
      preset: subject ? "keep" : "padrao_2026",
      lab: subject?.exam_requires_lab ?? false,
    });
    setProgress({});
    if (subject) {
      api.get<PortalProgress | null>(`/subjects/${subject.id}/portal-progress`).then((pp) => {
        const values: Record<string, string> = { percent: pp?.percent?.toString() ?? "" };
        NUM_FIELDS.forEach(({ key }) => (values[key] = pp?.[key]?.toString() ?? ""));
        setProgress(values);
      });
    }
  }, [open, subject]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("Informe o nome da disciplina.");
      return;
    }
    try {
      const rule =
        form.preset === "keep"
          ? (subject?.grading_rule ?? null)
          : (presets as Record<string, Record<string, unknown>>)[form.preset];
      const body = {
        degree_id: subject?.degree_id ?? degreeId,
        component_id: subject?.component_id ?? null,
        semester_id: form.semester === "none" ? null : Number(form.semester),
        name: form.name.trim(),
        code: form.code.trim() || null,
        hours: toNum(form.hours),
        status: form.status,
        grading_rule: rule,
        exam_requires_lab: form.lab,
        notes: subject?.notes ?? null,
      };
      const saved = subject
        ? await api.put<Subject>(`/subjects/${subject.id}`, body)
        : await api.post<Subject>("/subjects", body);
      if (Object.keys(progress).length > 0) {
        const pp: Record<string, number | string | null> = { percent: toNum(progress.percent ?? "") };
        NUM_FIELDS.forEach(({ key }) => (pp[key] = toNum(progress[key] ?? "")));
        pp.as_of = new Date().toISOString().slice(0, 10);
        await api.put(`/subjects/${saved.id}/portal-progress`, pp);
      }
      toast.success("Disciplina salva");
      onSaved();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar");
    }
  };

  const set = (key: keyof typeof form) => (v: string | boolean) => setForm((f) => ({ ...f, [key]: v }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={subject ? "Editar disciplina" : "Nova disciplina"}>
        <form onSubmit={save} className="grid grid-cols-1 gap-4" noValidate>
          <Field id="s-name" label="Nome" error={error}>
            {(d) => (
              <Input
                id="s-name"
                value={form.name}
                onChange={(e) => set("name")(e.target.value)}
                aria-describedby={d}
                aria-invalid={!!error}
              />
            )}
          </Field>
          <Field id="s-code" label="Código" optional>
            {() => <Input id="s-code" value={form.code} onChange={(e) => set("code")(e.target.value)} />}
          </Field>
          <Field id="s-hours" label="Carga horária (h)" optional>
            {() => <Input id="s-hours" inputMode="numeric" value={form.hours} onChange={(e) => set("hours")(e.target.value)} />}
          </Field>
          <Field id="s-semester" label="Semestre">
            {() => (
              <Select
                id="s-semester"
                value={form.semester}
                onValueChange={set("semester")}
                options={[
                  { value: "none", label: "Sem semestre (pendente)" },
                  ...semesters.map((s) => ({ value: String(s.id), label: s.code })),
                ]}
              />
            )}
          </Field>
          <Field id="s-status" label="Situação">
            {() => (
              <Select
                id="s-status"
                value={form.status}
                onValueChange={set("status")}
                options={Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))}
              />
            )}
          </Field>
          <Field
            id="s-rule"
            label="Regra de avaliação"
            hint="Modelos de exemplo. Ajuste aos planos de ensino da sua faculdade."
          >
            {(d) => (
              <Select
                id="s-rule"
                value={form.preset}
                onValueChange={set("preset")}
                aria-describedby={d}
                options={[
                  ...(subject
                    ? [{ value: "keep", label: `Manter: ${(subject.grading_rule?.label as string) ?? "sem regra"}` }]
                    : []),
                  ...Object.entries(presets).map(([value, p]) => ({ value, label: p.label })),
                ]}
              />
            )}
          </Field>
          <CheckboxRow id="s-lab" checked={form.lab} onCheckedChange={set("lab")}>
            A prova só é liberada depois do laboratório
          </CheckboxRow>

          {subject && (
            <>
              <Separator />
              <h3 className="text-sm font-semibold">Progresso no portal</h3>
              <Field id="pp-percent" label="Progresso geral (%)" optional>
                {() => (
                  <Input
                    id="pp-percent"
                    inputMode="decimal"
                    value={progress.percent ?? ""}
                    onChange={(e) => setProgress((p) => ({ ...p, percent: e.target.value }))}
                  />
                )}
              </Field>
              <div className="grid grid-cols-2 gap-4">
                {NUM_FIELDS.map(({ key, label }) => (
                  <Field key={key} id={`pp-${key}`} label={label} optional>
                    {() => (
                      <Input
                        id={`pp-${key}`}
                        inputMode="numeric"
                        value={progress[key] ?? ""}
                        onChange={(e) => setProgress((p) => ({ ...p, [key]: e.target.value }))}
                      />
                    )}
                  </Field>
                ))}
              </div>
            </>
          )}

          <div className="flex gap-3 pt-2">
            <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
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
