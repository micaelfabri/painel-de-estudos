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
const FIELDS: {
  key: string;
  label: string;
  kind: "number" | "text" | "model" | "bool";
  optional?: boolean;
}[] = [
  {
    key: "weekly_hours_goal",
    label: "Meta de horas por semana",
    kind: "number",
    optional: true,
  },
  // v1.8 (D40, D41): cursos fora da faculdade têm meta própria e só entram no dia se ligar
  {
    key: "course_weekly_goal_hours",
    label: "Meta de horas por semana em cursos",
    kind: "number",
    optional: true,
  },
  { key: "courses_in_day_plan", label: 'Incluir os cursos em "Montar o dia"', kind: "bool" },
  {
    key: "timer_goal_minutes",
    label: "Meta do cronômetro por tema (min)",
    kind: "number",
  },
  {
    key: "timer_alarm_minutes",
    label: "Alarme do cronômetro (min)",
    kind: "number",
  },
  {
    key: "llm_base_url",
    label: "Endereço do modelo local (API compatível com OpenAI)",
    kind: "text",
  },
  {
    key: "default_model",
    label: "Modelo padrão do agente",
    kind: "model",
    optional: true,
  },
  {
    key: "llm_timeout_seconds",
    label: "Tempo máximo de resposta do modelo (s)",
    kind: "number",
  },
  {
    key: "options_per_question",
    label: "Alternativas por questão",
    kind: "number",
    optional: true,
  },
  { key: "questions_per_set", label: "Questões por conjunto", kind: "number" },
  { key: "exam_minutes", label: "Tempo do simulado (min)", kind: "number" },
  { key: "agent_reads_metrics", label: "O agente pode ler meus números de estudo", kind: "bool" },
  {
    key: "vision_model",
    label: "Modelo que lê imagens (notas pelos prints)",
    kind: "model",
    optional: true,
  },
  { key: "github_url", label: "GitHub (rodapé)", kind: "text", optional: true },
  {
    key: "linkedin_url",
    label: "LinkedIn (rodapé)",
    kind: "text",
    optional: true,
  },
  {
    key: "site_url",
    label: "Site pessoal (rodapé)",
    kind: "text",
    optional: true,
  },
];

// Select não aceita valor vazio: "usar o padrão" vira null ao salvar
const NONE = "__none";

/** Gerenciar › Configurações */
export function SettingsPage() {
  const settings = useApi<SettingsResponse>("/settings");
  const models = useApi<ModelsInfo>("/agent/models");
  const [values, setValues] = React.useState<Record<string, string>>({});
  const [errors, setErrors] = React.useState<Record<string, string>>({});

  React.useEffect(() => {
    if (!settings.data) return;
    const v: Record<string, string> = {};
    FIELDS.forEach(
      ({ key }) => (v[key] = settings.data!.values[key] == null ? "" : String(settings.data!.values[key])),
    );
    setValues(v);
  }, [settings.data]);

  const describe = (key: string) => settings.data?.schema.find((s) => s.key === key)?.description;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const next: Record<string, string> = {};
    for (const f of FIELDS) {
      const raw = values[f.key] === NONE ? "" : (values[f.key]?.trim() ?? "");
      const value =
        f.kind === "bool"
          ? raw === "true"
          : raw === ""
            ? null
            : f.kind === "number"
              ? Number(raw.replace(",", "."))
              : raw;
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
                  f.kind === "bool" ? (
                    <Select
                      id={`set-${f.key}`}
                      aria-describedby={d}
                      value={values[f.key] === "true" ? "true" : "false"}
                      onValueChange={(v) => setValues((x) => ({ ...x, [f.key]: v }))}
                      options={[
                        { value: "false", label: "Não" },
                        { value: "true", label: "Sim" },
                      ]}
                    />
                  ) : f.kind === "model" ? (
                    <Select
                      id={`set-${f.key}`}
                      aria-describedby={d}
                      value={values[f.key] ?? ""}
                      placeholder={models.data?.reachable ? "Escolha" : "Modelo local fora do ar"}
                      disabled={!models.data?.reachable}
                      onValueChange={(v) => setValues((x) => ({ ...x, [f.key]: v }))}
                      options={[
                        ...(f.optional
                          ? [
                              {
                                value: NONE,
                                label: f.key === "vision_model" ? "Usar o modelo padrão" : "Nenhum",
                              },
                            ]
                          : []),
                        ...(models.data?.models ?? []).map((m) => ({
                          value: m,
                          label: m,
                        })),
                      ]}
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
      <VisionCheck />
      <IntegrationsCard />
      <UsageLog />
    </div>
  );
}

/** Confere se o modelo escolhido lê imagens antes de confiar nas notas pelos prints (SPEC D17) */
function VisionCheck() {
  const [state, setState] = React.useState<{
    ok: boolean;
    message: string;
    model: string | null;
  } | null>(null);
  const [busy, setBusy] = React.useState(false);
  const run = async () => {
    setBusy(true);
    try {
      setState(await api.post("/prints/check-vision", {}));
    } catch (err) {
      setState({
        ok: false,
        model: null,
        message: err instanceof Error ? err.message : "Não foi possível testar.",
      });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card>
      <CardContent className="space-y-3">
        <h2 className="text-lg font-semibold">Leitura de imagens</h2>
        <p className="text-sm text-muted-foreground">
          As notas pelos prints usam o modelo local para ler cada imagem. Teste antes: mando uma imagem com um número e
          confiro se o modelo acerta.
        </p>
        <Button variant="outline" onClick={run} disabled={busy}>
          {busy ? "Testando…" : "Testar leitura de imagem"}
        </Button>
        {state && (
          <p role="status" className={`text-sm ${state.ok ? "text-success-text" : "text-warning-text"}`}>
            {state.model ? `${state.model}: ` : ""}
            {state.message}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
