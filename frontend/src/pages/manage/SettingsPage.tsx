import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { IntegrationsCard } from "@/components/manage/IntegrationsCard";
import { UsageLog } from "@/components/manage/UsageLog";
import { Select } from "@/components/ui/select";
import { api, type ModelsInfo, type SettingsResponse } from "@/lib/api";
import { useApi } from "@/lib/useApi";

// Configurações editáveis. As integrações (Notion, Agenda) entram na F5.
const FIELDS: { key: string; label: string; kind: "number" | "text" | "model"; optional?: boolean }[] = [
  { key: "weekly_hours_goal", label: "Meta de horas por semana", kind: "number", optional: true },
  { key: "timer_goal_minutes", label: "Meta do cronômetro por tema (min)", kind: "number" },
  { key: "timer_alarm_minutes", label: "Alarme do cronômetro (min)", kind: "number" },
  { key: "llm_base_url", label: "Endereço do modelo local (API compatível com OpenAI)", kind: "text" },
  { key: "default_model", label: "Modelo padrão do agente", kind: "model", optional: true },
  { key: "llm_timeout_seconds", label: "Tempo máximo de resposta do modelo (s)", kind: "number" },
  { key: "options_per_question", label: "Alternativas por questão", kind: "number", optional: true },
  { key: "questions_per_set", label: "Questões por conjunto", kind: "number" },
];

/** Gerenciar › Configurações */
export function SettingsPage() {
  const settings = useApi<SettingsResponse>("/settings");
  const models = useApi<ModelsInfo>("/agent/models");
  const [values, setValues] = React.useState<Record<string, string>>({});
  const [errors, setErrors] = React.useState<Record<string, string>>({});

  React.useEffect(() => {
    if (!settings.data) return;
    const v: Record<string, string> = {};
    FIELDS.forEach(({ key }) => (v[key] = settings.data!.values[key] == null ? "" : String(settings.data!.values[key])));
    setValues(v);
  }, [settings.data]);

  const describe = (key: string) => settings.data?.schema.find((s) => s.key === key)?.description;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const next: Record<string, string> = {};
    for (const f of FIELDS) {
      const raw = values[f.key]?.trim() ?? "";
      const value = raw === "" ? null : f.kind === "number" ? Number(raw.replace(",", ".")) : raw;
      try {
        await api.put(`/settings/${f.key}`, { value });
      } catch (err) {
        next[f.key] = err instanceof Error ? "Valor inválido" : "Erro";
      }
    }
    setErrors(next);
    if (Object.keys(next).length === 0) toast.success("Configurações salvas");
    void settings.reload();
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Configurações</h1>
        <p className="text-sm text-muted-foreground">Ficam no banco local deste PC.</p>
      </header>
      <Card>
        <CardContent>
          <form onSubmit={save} className="grid grid-cols-1 gap-4 md:grid-cols-2" noValidate>
            {FIELDS.map((f) => (
              <Field
                key={f.key}
                id={`set-${f.key}`}
                label={f.label}
                optional={f.optional}
                hint={describe(f.key)}
                error={errors[f.key]}
              >
                {(d) =>
                  f.kind === "model" ? (
                    <Select
                      id={`set-${f.key}`}
                      aria-describedby={d}
                      value={values[f.key] ?? ""}
                      placeholder={models.data?.reachable ? "Escolha" : "Modelo local fora do ar"}
                      disabled={!models.data?.reachable}
                      onValueChange={(v) => setValues((x) => ({ ...x, [f.key]: v }))}
                      options={(models.data?.models ?? []).map((m) => ({ value: m, label: m }))}
                    />
                  ) : (
                    <Input
                      id={`set-${f.key}`}
                      inputMode={f.kind === "number" ? "decimal" : undefined}
                      value={values[f.key] ?? ""}
                      aria-describedby={d}
                      aria-invalid={!!errors[f.key]}
                      onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                    />
                  )
                }
              </Field>
            ))}
            <div className="md:col-span-2">
              <Button type="submit">Salvar configurações</Button>
            </div>
          </form>
        </CardContent>
      </Card>
      <IntegrationsCard />
      <UsageLog />
    </div>
  );
}
