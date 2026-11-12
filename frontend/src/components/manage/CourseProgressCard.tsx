import { AlertTriangle, Pencil } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { InlineMeter } from "@/components/panel/InlineMeter";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { CheckboxRow } from "@/components/ui/checkbox";
import { api, type CourseComponent, type CourseProgress } from "@/lib/api";
import { formatDayMonth, formatNumber, parseLocalDate } from "@/lib/format";

const SOURCE: Record<CourseComponent["kind"], string> = {
  subjects: "histórico + disciplinas aprovadas aqui",
  acc: "soma das atividades complementares",
  manual: "valor digitado",
};

/** Progresso do curso por componente da carga horária (SPEC §6.6) */
export function CourseProgressCard({ data, onSaved }: { data: CourseProgress; onSaved: () => void }) {
  const [editing, setEditing] = React.useState<CourseComponent | null>(null);
  const total = data.degree.total_hours;
  return (
    <Card>
      <CardContent className="space-y-6">
        <div className="space-y-1">
          <CardTitle>Progresso do curso</CardTitle>
          <p className="text-sm text-muted-foreground">
            {data.degree.name} · {data.degree.institution} · currículo {data.degree.curriculum}
            {data.degree.reported_at &&
              ` · base no histórico de ${formatDayMonth(parseLocalDate(data.degree.reported_at))}/${data.degree.reported_at.slice(0, 4)}`}
          </p>
        </div>
        <div>
          <p className="text-2xl font-semibold tabular-nums">
            {formatNumber(data.done_hours)}h
            {total && <span className="text-sm font-normal text-muted-foreground"> de {formatNumber(total)}h</span>}
          </p>
          {data.percent !== null && <InlineMeter label="Carga horária concluída" hideLabel value={data.percent} />}
        </div>
        <ul className="space-y-4">
          {data.components.map((c) => (
            <li key={c.id} className="space-y-1">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium">
                  {c.name}
                  <span className="font-normal text-muted-foreground">
                    {" "}
                    · {formatNumber(c.done_hours)}h{c.required_hours !== null ? ` de ${formatNumber(c.required_hours)}h` : ""}
                  </span>
                </p>
                <Button variant="ghost" size="icon" aria-label={`Editar ${c.name}`} onClick={() => setEditing(c)}>
                  <Pencil aria-hidden="true" />
                </Button>
              </div>
              {c.percent !== null && <InlineMeter label={c.name} hideLabel value={Math.min(100, c.percent)} />}
              <p className="text-xs text-muted-foreground">
                {c.to_check && (
                  <span className="mr-1 inline-flex items-center gap-1 text-warning-text">
                    <AlertTriangle className="h-3 w-3" aria-hidden="true" />A conferir ·
                  </span>
                )}
                {SOURCE[c.kind]}
                {c.required_hours === null && " · total exigido não registrado"}
              </p>
            </li>
          ))}
        </ul>
      </CardContent>
      <ComponentDialog component={editing} onClose={() => setEditing(null)} onSaved={onSaved} degreeId={data.degree.id} />
    </Card>
  );
}

function ComponentDialog({
  component,
  degreeId,
  onClose,
  onSaved,
}: {
  component: CourseComponent | null;
  degreeId: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [v, setV] = React.useState({ required: "", baseline: "", toCheck: false });
  React.useEffect(() => {
    if (component)
      setV({
        required: component.required_hours?.toString() ?? "",
        baseline: String(component.baseline_hours),
        toCheck: component.to_check,
      });
  }, [component]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!component) return;
    try {
      await api.put(`/degree-components/${component.id}`, {
        degree_id: degreeId,
        name: component.name,
        kind: component.kind,
        required_hours: v.required.trim() === "" ? null : Number(v.required),
        done_hours: Number(v.baseline || 0),
        to_check: v.toCheck,
        notes: component.notes,
      });
      toast.success("Componente salvo");
      onSaved();
      onClose();
    } catch {
      toast.error("Não foi possível salvar. Confira os números.");
    }
  };

  return (
    <Dialog open={component !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={`Editar ${component?.name ?? ""}`} description="Atualize com o histórico mais recente do portal.">
        <form onSubmit={save} className="grid grid-cols-1 gap-4" noValidate>
          <Field id="c-req" label="Horas exigidas" optional>
            {() => (
              <Input
                id="c-req"
                inputMode="numeric"
                value={v.required}
                onChange={(e) => setV({ ...v, required: e.target.value })}
              />
            )}
          </Field>
          {component?.kind !== "acc" && (
            <Field
              id="c-base"
              label="Horas concluídas no histórico"
              hint="Disciplinas aprovadas no painel somam por cima deste valor."
            >
              {(d) => (
                <Input
                  id="c-base"
                  inputMode="numeric"
                  aria-describedby={d}
                  value={v.baseline}
                  onChange={(e) => setV({ ...v, baseline: e.target.value })}
                />
              )}
            </Field>
          )}
          <CheckboxRow id="c-check" checked={v.toCheck} onCheckedChange={(c) => setV({ ...v, toCheck: c })}>
            Valor a conferir com a faculdade
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
