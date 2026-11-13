import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { CheckboxRow } from "@/components/ui/checkbox";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, type Course, type CourseStatus, type CourseType } from "@/lib/api";

export const COURSE_TYPES: { value: CourseType; label: string }[] = [
  { value: "course_certificate", label: "Curso com certificado" },
  { value: "certification", label: "Certificação com prova" },
  { value: "language", label: "Idioma" },
  { value: "bootcamp", label: "Bootcamp" },
  { value: "free", label: "Curso livre" },
];

export const COURSE_STATUSES: { value: CourseStatus; label: string }[] = [
  { value: "doing", label: "Fazendo" },
  { value: "wishlist", label: "Quero fazer" },
  { value: "paused", label: "Pausado" },
  { value: "done", label: "Concluído" },
];

type Form = {
  name: string;
  platform: string;
  course_type: CourseType;
  course_status: CourseStatus;
  url: string;
  total_hours: string;
  modules: string;
  start_date: string;
  target_date: string;
  exam_at: string;
  manual_progress: string;
  counts_acc: boolean;
  acc_category: string;
  certificate_path: string;
  notion_page: string;
  notes: string;
};

const empty: Form = {
  name: "",
  platform: "",
  course_type: "course_certificate",
  course_status: "doing",
  url: "",
  total_hours: "",
  modules: "",
  start_date: "",
  target_date: "",
  exam_at: "",
  manual_progress: "",
  counts_acc: false,
  acc_category: "Cursos",
  certificate_path: "",
  notion_page: "",
  notes: "",
};

function fromCourse(c: Course): Form {
  return {
    name: c.name,
    platform: c.platform ?? "",
    course_type: c.course_type,
    course_status: c.course_status,
    url: c.url ?? "",
    total_hours: c.total_hours !== null ? String(c.total_hours) : "",
    modules: "",
    start_date: c.start_date ?? "",
    target_date: c.target_date ?? "",
    exam_at: c.exam_at ? c.exam_at.slice(0, 16) : "",
    manual_progress: c.manual_progress !== null ? String(c.manual_progress) : "",
    counts_acc: c.counts_acc,
    acc_category: c.acc_category ?? "",
    certificate_path: c.certificate_path ?? "",
    notion_page: c.notion_page_id ?? "",
    notes: c.notes ?? "",
  };
}

const toInt = (v: string) => (v.trim() === "" ? null : Math.round(Number(v.replace(",", "."))));

/** v1.8 (D39): formulário de curso — novo (com N módulos) ou edição */
export function CourseDialog({
  open,
  course,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  course?: Course | null;
  onOpenChange: (open: boolean) => void;
  onSaved: (course: Course) => void;
}) {
  const [v, setV] = React.useState<Form>(empty);
  const [error, setError] = React.useState<string>();
  const [busy, setBusy] = React.useState(false);
  const set = (patch: Partial<Form>) => setV((s) => ({ ...s, ...patch }));

  React.useEffect(() => {
    if (open) {
      setError(undefined);
      setV(course ? fromCourse(course) : empty);
    }
  }, [open, course]);

  const noModules = course ? course.modules_total === 0 : (toInt(v.modules) ?? 0) === 0;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!v.name.trim()) return setError("Informe o nome do curso.");
    if (v.url.trim() && !v.url.trim().toLowerCase().startsWith("https://"))
      return setError("O link do curso precisa começar com https://");
    const hours = toInt(v.total_hours);
    const modules = toInt(v.modules) ?? 0;
    const progress = toInt(v.manual_progress);
    if (hours !== null && (Number.isNaN(hours) || hours < 0)) return setError("Carga horária inválida.");
    if (Number.isNaN(modules) || modules < 0 || modules > 50) return setError("Módulos: de 0 a 50.");
    if (progress !== null && (Number.isNaN(progress) || progress < 0 || progress > 100))
      return setError("Progresso: de 0 a 100.");
    const body = {
      name: v.name.trim(),
      platform: v.platform.trim() || null,
      course_type: v.course_type,
      course_status: v.course_status,
      url: v.url.trim() || null,
      total_hours: hours,
      start_date: v.start_date || null,
      target_date: v.target_date || null,
      exam_at: v.course_type === "certification" && v.exam_at ? v.exam_at : null,
      manual_progress: noModules ? progress : null,
      counts_acc: v.counts_acc,
      acc_category: v.counts_acc ? v.acc_category.trim() || null : null,
      certificate_path: v.certificate_path.trim() || null,
      notion_page: v.notion_page.trim() || null,
      notes: v.notes.trim() || null,
      ...(course ? {} : { modules }),
    };
    setBusy(true);
    setError(undefined);
    try {
      const saved = course
        ? await api.put<Course>(`/courses/${course.id}`, body)
        : await api.post<Course>("/courses", body);
      toast.success(course ? "Curso salvo" : "Curso criado");
      onSaved(saved);
      onOpenChange(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      // Erro de validação vem como lista em JSON: mostra uma frase amigável
      setError(msg && !msg.startsWith("[") ? msg : "Confira os campos: algum valor não foi aceito.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogContent
        title={course ? "Editar curso" : "Novo curso"}
        description="Fica em Cursos e certificados, separado da faculdade."
      >
        <form onSubmit={save} className="space-y-4" noValidate>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field id="c-name" label="Nome">
                {() => <Input id="c-name" value={v.name} onChange={(e) => set({ name: e.target.value })} />}
              </Field>
            </div>
            <Field id="c-platform" label="Plataforma" optional>
              {() => <Input id="c-platform" value={v.platform} onChange={(e) => set({ platform: e.target.value })} />}
            </Field>
            <Field id="c-type" label="Tipo">
              {() => (
                <Select
                  id="c-type"
                  value={v.course_type}
                  onValueChange={(t) => set({ course_type: t as CourseType })}
                  options={COURSE_TYPES}
                />
              )}
            </Field>
            <Field id="c-status" label="Situação">
              {() => (
                <Select
                  id="c-status"
                  value={v.course_status}
                  onValueChange={(t) => set({ course_status: t as CourseStatus })}
                  options={COURSE_STATUSES}
                />
              )}
            </Field>
            <Field id="c-hours" label="Carga horária" optional hint="Em horas">
              {(d) => (
                <Input
                  id="c-hours"
                  aria-describedby={d}
                  inputMode="numeric"
                  value={v.total_hours}
                  onChange={(e) => set({ total_hours: e.target.value })}
                />
              )}
            </Field>
            <div className="sm:col-span-2">
              <Field id="c-url" label="Link do curso" optional>
                {() => (
                  <Input
                    id="c-url"
                    type="url"
                    placeholder="https://"
                    value={v.url}
                    onChange={(e) => set({ url: e.target.value })}
                  />
                )}
              </Field>
            </div>
            {!course && (
              <Field id="c-modules" label="Módulos" optional hint='Viram os "temas" do curso; dá para mudar depois'>
                {(d) => (
                  <Input
                    id="c-modules"
                    aria-describedby={d}
                    inputMode="numeric"
                    value={v.modules}
                    onChange={(e) => set({ modules: e.target.value })}
                  />
                )}
              </Field>
            )}
            {noModules && (
              <Field id="c-progress" label="Progresso (%)" optional hint="Para curso sem módulos, como idioma">
                {(d) => (
                  <Input
                    id="c-progress"
                    aria-describedby={d}
                    inputMode="numeric"
                    value={v.manual_progress}
                    onChange={(e) => set({ manual_progress: e.target.value })}
                  />
                )}
              </Field>
            )}
            <Field id="c-start" label="Começou em" optional>
              {() => (
                <Input
                  id="c-start"
                  type="date"
                  value={v.start_date}
                  onChange={(e) => set({ start_date: e.target.value })}
                />
              )}
            </Field>
            <Field id="c-target" label="Meta de conclusão" optional>
              {() => (
                <Input
                  id="c-target"
                  type="date"
                  value={v.target_date}
                  onChange={(e) => set({ target_date: e.target.value })}
                />
              )}
            </Field>
            {v.course_type === "certification" && (
              <Field id="c-exam" label="Data da prova" optional hint="Fica só na área de cursos">
                {(d) => (
                  <Input
                    id="c-exam"
                    aria-describedby={d}
                    type="datetime-local"
                    value={v.exam_at}
                    onChange={(e) => set({ exam_at: e.target.value })}
                  />
                )}
              </Field>
            )}
            <div className="sm:col-span-2">
              <Field
                id="c-cert"
                label="Caminho do certificado"
                optional
                hint="Na pasta de materiais, ex.: D:\Cursos\…\certificado.pdf"
              >
                {(d) => (
                  <Input
                    id="c-cert"
                    aria-describedby={d}
                    value={v.certificate_path}
                    onChange={(e) => set({ certificate_path: e.target.value })}
                  />
                )}
              </Field>
            </div>
            <div className="space-y-2 rounded-md border border-border p-3 sm:col-span-2">
              <CheckboxRow id="c-acc" checked={v.counts_acc} onCheckedChange={(on) => set({ counts_acc: on })}>
                <span className="font-medium">Conta como AAC da faculdade</span>
                <span className="block text-xs text-muted-foreground">
                  Ao concluir, o curso oferece lançar as horas em Atividades complementares.
                </span>
              </CheckboxRow>
              {v.counts_acc && (
                <Field id="c-acc-cat" label="Categoria da AAC" optional>
                  {() => (
                    <Input
                      id="c-acc-cat"
                      value={v.acc_category}
                      onChange={(e) => set({ acc_category: e.target.value })}
                    />
                  )}
                </Field>
              )}
            </div>
            <div className="sm:col-span-2">
              <Field id="c-notion" label="Página do Notion" optional hint="Cole o link da página">
                {(d) => (
                  <Input
                    id="c-notion"
                    aria-describedby={d}
                    value={v.notion_page}
                    onChange={(e) => set({ notion_page: e.target.value })}
                  />
                )}
              </Field>
            </div>
            <div className="sm:col-span-2">
              <Field id="c-notes" label="Observações" optional>
                {() => <Textarea id="c-notes" value={v.notes} onChange={(e) => set({ notes: e.target.value })} />}
              </Field>
            </div>
          </div>
          {error && (
            <p role="alert" className="text-sm text-destructive-text">
              {error}
            </p>
          )}
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" className="flex-1" disabled={busy}>
              {course ? "Salvar" : "Salvar curso"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
