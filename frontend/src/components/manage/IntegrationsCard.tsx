import { CalendarCheck, CheckCircle2, CircleAlert, Info, RefreshCw } from "lucide-react";
import * as React from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckboxRow } from "@/components/ui/checkbox";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { api, type ExamSyncPreview, type GoogleStatus, type NotionStatus } from "@/lib/api";
import { formatDayMonth, formatTime, parseLocalDateTime } from "@/lib/format";
import { useApi } from "@/lib/useApi";

/** Configurações › Integrações (F5): Notion e Google Agenda. Credenciais ficam no .env e em secrets/. */
export function IntegrationsCard() {
  const notion = useApi<NotionStatus>("/notion/status");
  const google = useApi<GoogleStatus>("/google/status");
  const [params, setParams] = useSearchParams();
  const [busy, setBusy] = React.useState<"notion" | "google" | null>(null);

  // Volta do login do Google: /gerenciar/configuracoes?google=ok|erro|cancelado
  React.useEffect(() => {
    const result = params.get("google");
    if (!result) return;
    if (result === "ok") toast.success("Google conectado");
    else if (result === "erro") toast.error("Não foi possível conectar o Google. Tente de novo.");
    params.delete("google");
    setParams(params, { replace: true });
  }, [params, setParams]);

  const syncNotion = async () => {
    setBusy("notion");
    try {
      const out = await api.post<{ ok: number; errors: string[] }>("/notion/sync", {});
      if (out.errors.length) toast.error(out.errors[0]);
      else toast.success(out.ok ? `${out.ok} resultado(s) gravado(s) no Notion` : "Nada pendente");
      void notion.reload();
    } finally {
      setBusy(null);
    }
  };

  // v1.5: antes de mandar, lista as provas e só vão as marcadas (eu já crio as minhas na agenda)
  const [preview, setPreview] = React.useState<ExamSyncPreview[] | null>(null);
  const [chosen, setChosen] = React.useState<Set<number>>(new Set());

  const openSync = async () => {
    try {
      const list = await api.get<ExamSyncPreview[]>("/google/sync-exams/preview");
      setChosen(new Set(list.filter((e) => e.sent).map((e) => e.id)));
      setPreview(list);
    } catch {
      toast.error("Não foi possível listar as provas.");
    }
  };

  const [syncError, setSyncError] = React.useState<string | null>(null);
  const syncExams = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy("google");
    setSyncError(null);
    try {
      const out = await api.post<{ created: number; updated: number }>("/google/sync-exams", {
        exam_ids: [...chosen],
      });
      toast.success(`Agenda atualizada: ${out.created} prova(s) criada(s), ${out.updated} atualizada(s)`);
      setPreview(null);
      void google.reload();
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : "Não foi possível falar com o Google");
    } finally {
      setBusy(null);
    }
  };

  const n = notion.data;
  const g = google.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Integrações</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-6 md:grid-cols-2">
        <section aria-labelledby="int-notion" className="space-y-3">
          <h3 id="int-notion" className="font-medium">
            Notion
          </h3>
          {n && (
            <Status
              ok={n.reachable}
              text={
                !n.configured
                  ? "Falta o NOTION_TOKEN no arquivo .env (guia, seção 7)."
                  : n.reachable
                    ? `Conectado: ${n.pages} página(s) compartilhada(s) com a conexão.`
                    : (n.error ?? "Notion fora do ar.")
              }
            />
          )}
          <p className="text-sm text-muted-foreground">
            Ligue cada tema à página dele em Disciplinas e temas. Ao fechar um conjunto de questões, o resultado entra
            no fim da página; nada é apagado.
          </p>
          {n && n.pending_results > 0 && (
            <Button variant="outline" onClick={syncNotion} disabled={busy !== null}>
              <RefreshCw aria-hidden="true" />
              Gravar {n.pending_results} resultado(s) pendente(s)
            </Button>
          )}
        </section>

        <section aria-labelledby="int-google" className="space-y-3">
          <h3 id="int-google" className="font-medium">
            Google Agenda
          </h3>
          {g && (
            <Status
              ok={g.connected}
              text={
                !g.client_file
                  ? "Falta o arquivo secrets/google_client.json (guia, seção 7)."
                  : g.connected
                    ? `Conectado. As provas vão para a agenda "${g.calendar_name}".`
                    : "Ainda não conectado."
              }
            />
          )}
          <p className="text-sm text-muted-foreground">
            O painel só escreve na agenda própria dele e só lê a principal. Nunca apaga eventos. Se o Google pedir login
            de novo (app em teste: a cada ~7 dias), clique em Conectar Google.
          </p>
          <div className="flex flex-wrap gap-3">
            {g?.client_file && (
              <Button variant={g.connected ? "outline" : "default"} asChild>
                <a href="/api/google/login">{g.connected ? "Conectar de novo" : "Conectar Google"}</a>
              </Button>
            )}
            {g?.connected && (
              <Button onClick={openSync} disabled={busy !== null}>
                <CalendarCheck aria-hidden="true" />
                Mandar provas para a agenda
              </Button>
            )}
          </div>
        </section>
      </CardContent>
      <Dialog open={preview !== null} onOpenChange={(v) => !v && setPreview(null)}>
        <DialogContent
          title="Mandar provas para a agenda"
          description="Marque só as provas que ainda não estão na sua agenda."
        >
          <form onSubmit={syncExams} className="space-y-4">
            <div role="note" className="flex items-start gap-2 rounded-md border bg-muted/50 p-3">
              <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <p className="text-sm text-foreground">
                Vão para a agenda "{g?.calendar_name ?? "do painel"}". Deixe desmarcadas as provas que você já criou,
                para não duplicar. Nada é apagado.
              </p>
            </div>
            {preview?.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhuma prova com data e hora marcadas.</p>
            ) : (
              <fieldset>
                <legend className="sr-only">Provas</legend>
                {preview?.map((e) => {
                  const d = parseLocalDateTime(e.scheduled_at);
                  return (
                    <CheckboxRow
                      key={e.id}
                      id={`sync-${e.id}`}
                      checked={chosen.has(e.id)}
                      onCheckedChange={(v) =>
                        setChosen((set) => {
                          const next = new Set(set);
                          if (v) next.add(e.id);
                          else next.delete(e.id);
                          return next;
                        })
                      }
                      trailing={e.sent ? <span className="text-xs text-muted-foreground">já enviada</span> : null}
                    >
                      {e.title} · {formatDayMonth(d)} {formatTime(d)}
                    </CheckboxRow>
                  );
                })}
              </fieldset>
            )}
            {syncError && (
              <p role="alert" className="text-sm text-destructive-text">
                {syncError}
              </p>
            )}
            <div className="flex gap-3">
              <Button type="button" variant="secondary" className="flex-1" onClick={() => setPreview(null)}>
                Cancelar
              </Button>
              <Button type="submit" className="flex-1" disabled={chosen.size === 0 || busy !== null}>
                {chosen.size ? `Mandar ${chosen.size} prova(s)` : "Marque uma prova"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function Status({ ok, text }: { ok: boolean; text: string }) {
  const Icon = ok ? CheckCircle2 : CircleAlert;
  return (
    <p className={`flex items-start gap-2 text-sm ${ok ? "text-success-text" : "text-warning-text"}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <span>{text}</span>
    </p>
  );
}
