import { ChevronLeft, FileText, Folder, Image as ImageIcon } from "lucide-react";
import * as React from "react";

import { useAgent } from "@/components/agent/AgentContext";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select } from "@/components/ui/select";
import { agentErrorMessage, api, type CardView, type FolderListing, type Topic } from "@/lib/api";

type Source = "notion" | "folder" | "file" | "paste";

const SOURCES: [Source, string][] = [
  ["notion", "Prints da página do tema no Notion"],
  ["folder", "Prints da pasta de materiais"],
  ["file", "Transcrição de vídeo (arquivo .vtt, .srt ou .txt)"],
  ["paste", "Transcrição colada"],
];

/** Navegador da pasta de materiais: prints (vários) ou transcrição (um arquivo) */
function FolderBrowser({
  kind,
  picked,
  onPick,
}: {
  kind: "prints" | "transcripts";
  picked: string[];
  onPick: (paths: string[]) => void;
}) {
  const [folder, setFolder] = React.useState<FolderListing | null>(null);
  const [error, setError] = React.useState<string>();
  const open = React.useCallback(
    async (path: string) => {
      setError(undefined);
      try {
        setFolder(await api.get<FolderListing>(`/prints/folder?path=${encodeURIComponent(path)}&kind=${kind}`));
        onPick([]);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Não foi possível abrir a pasta.");
      }
    },
    [kind, onPick],
  );
  React.useEffect(() => {
    void open("");
  }, [open]);

  if (error)
    return (
      <p role="alert" className="text-sm text-destructive-text">
        {error}
      </p>
    );
  if (!folder) return <p className="text-sm text-muted-foreground">Abrindo a pasta…</p>;
  const toggle = (path: string, on: boolean) =>
    onPick(kind === "transcripts" ? (on ? [path] : []) : on ? [...picked, path] : picked.filter((p) => p !== path));

  return (
    <Card className="p-3">
      <div className="mb-2 flex items-center gap-2">
        {folder.path && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Voltar uma pasta"
            onClick={() => open(folder.path.split("/").slice(0, -1).join("/"))}
          >
            <ChevronLeft aria-hidden="true" />
          </Button>
        )}
        <p className="truncate text-xs text-muted-foreground">{folder.path || "Pasta de materiais"}</p>
      </div>
      {folder.entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nada aqui.</p>
      ) : (
        <ul className="max-h-56 space-y-1 overflow-y-auto">
          {folder.entries.map((e) =>
            e.type === "dir" ? (
              <li key={e.path}>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="w-full justify-start"
                  onClick={() => open(e.path)}
                >
                  <Folder aria-hidden="true" />
                  {e.name}
                </Button>
              </li>
            ) : (
              <li key={e.path}>
                <Label
                  htmlFor={`cf-${e.path}`}
                  className="flex min-h-11 cursor-pointer items-center gap-3 px-3 sm:min-h-0 sm:py-1"
                >
                  <Checkbox
                    id={`cf-${e.path}`}
                    checked={picked.includes(e.path)}
                    onCheckedChange={(c) => toggle(e.path, c === true)}
                  />
                  {e.type === "image" ? (
                    <ImageIcon className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <FileText className="h-4 w-4" aria-hidden="true" />
                  )}
                  <span className="truncate text-sm font-normal">{e.name}</span>
                </Label>
              </li>
            ),
          )}
        </ul>
      )}
      <p className="mt-2 text-xs text-muted-foreground">
        {kind === "transcripts"
          ? picked.length
            ? "Transcrição escolhida."
            : "Escolha o arquivo de legenda ou transcrição do vídeo."
          : picked.length
            ? `${picked.length} arquivo(s) escolhido(s).`
            : folder.path
              ? "Sem escolher arquivos, leio todas as imagens e PDFs desta pasta."
              : "Entre na pasta da disciplina e escolha os prints."}
      </p>
    </Card>
  );
}

/**
 * Cards a partir de prints (C2) e de transcrições de vídeo (C4), autorizados em 12/11/2026 (D36).
 * Tudo vai só para o modelo local.
 */
export function CardSourcesDialog({
  open,
  onOpenChange,
  subjects,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  subjects: { id: number; name: string }[];
  onCreated: (cards: CardView[], skipped: number) => void;
}) {
  const { model } = useAgent();
  const [subjectId, setSubjectId] = React.useState("");
  const [topics, setTopics] = React.useState<Topic[]>([]);
  const [topicId, setTopicId] = React.useState("");
  const [source, setSource] = React.useState<Source>("folder");
  const [picked, setPicked] = React.useState<string[]>([]);
  const [text, setText] = React.useState("");
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string>();

  React.useEffect(() => {
    if (!subjectId) return;
    setTopicId("");
    api
      .get<Topic[]>(`/topics?subject_id=${subjectId}`)
      .then(setTopics)
      .catch(() => setTopics([]));
  }, [subjectId]);

  const topic = topics.find((t) => String(t.id) === topicId);
  const ready =
    topicId !== "" &&
    busy === null &&
    (source === "notion"
      ? !!topic?.notion_page_id
      : source === "paste"
        ? text.trim().length > 20
        : source === "file"
          ? picked.length === 1
          : true);

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setError(undefined);
    setBusy(
      source === "notion" || source === "folder"
        ? "O modelo está lendo os prints, um por um. Pode levar alguns minutos…"
        : "O modelo está montando os cards da transcrição…",
    );
    try {
      if (source === "notion" || source === "folder") {
        const out = await api.post<{ cards: CardView[]; skipped: unknown[] }>("/cards/from-prints", {
          topic_id: Number(topicId),
          source,
          paths: picked,
          model,
        });
        onCreated(out.cards, out.skipped.length);
      } else {
        const out = await api.post<{ cards: CardView[] }>("/cards/from-transcript", {
          topic_id: Number(topicId),
          path: source === "file" ? picked[0] : null,
          text: source === "paste" ? text : null,
          model,
        });
        onCreated(out.cards, 0);
      }
      onOpenChange(false);
    } catch (err) {
      setError(agentErrorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => busy === null && onOpenChange(v)}>
      <DialogContent
        title="Cards de prints ou de vídeo"
        description="Os prints e as transcrições vão só para o modelo local."
      >
        <form onSubmit={submit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="cs-subject" label="Disciplina">
              {() => (
                <Select
                  id="cs-subject"
                  value={subjectId}
                  onValueChange={setSubjectId}
                  placeholder="Escolha"
                  options={subjects.map((s) => ({ value: String(s.id), label: s.name }))}
                />
              )}
            </Field>
            <Field id="cs-topic" label="Tema">
              {() => (
                <Select
                  id="cs-topic"
                  value={topicId}
                  onValueChange={setTopicId}
                  placeholder={subjectId ? "Escolha" : "Escolha a disciplina antes"}
                  disabled={!subjectId}
                  options={topics.map((t) => ({ value: String(t.id), label: t.title }))}
                />
              )}
            </Field>
          </div>
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">De onde</legend>
            <RadioGroup
              value={source}
              onValueChange={(v) => {
                setSource(v as Source);
                setPicked([]);
              }}
            >
              {SOURCES.map(([value, label]) => (
                <label
                  key={value}
                  htmlFor={`cs-src-${value}`}
                  className="flex min-h-11 cursor-pointer items-center gap-3 sm:min-h-0"
                >
                  <RadioGroupItem id={`cs-src-${value}`} value={value} />
                  <span className="text-sm">{label}</span>
                </label>
              ))}
            </RadioGroup>
          </fieldset>

          {source === "notion" && topic && !topic.notion_page_id && (
            <p className="text-sm text-muted-foreground">
              Este tema não tem página do Notion ligada. Ligue em Gerenciar › Disciplinas e temas.
            </p>
          )}
          {source === "notion" && topic?.notion_page_id && (
            <p className="text-sm text-muted-foreground">
              Leio as imagens da página do tema e faço um card de cada questão que você errou.
            </p>
          )}
          {source === "folder" && <FolderBrowser kind="prints" picked={picked} onPick={setPicked} />}
          {source === "file" && <FolderBrowser kind="transcripts" picked={picked} onPick={setPicked} />}
          {source === "paste" && (
            <Field id="cs-text" label="Transcrição do vídeo">
              {(describedBy) => (
                <Textarea
                  id="cs-text"
                  aria-describedby={describedBy}
                  rows={6}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Cole a legenda ou a transcrição. Linhas com [mm:ss] ou no formato de legenda viram o minuto do card."
                />
              )}
            </Field>
          )}

          {error && (
            <p role="alert" className="text-sm text-destructive-text">
              {error}
            </p>
          )}
          {busy && (
            <p role="status" className="text-sm text-muted-foreground">
              {busy}
            </p>
          )}
          <div className="flex gap-3">
            <Button
              type="button"
              variant="secondary"
              className="flex-1"
              disabled={busy !== null}
              onClick={() => onOpenChange(false)}
            >
              Cancelar
            </Button>
            <Button type="submit" className="flex-1" disabled={!ready}>
              Criar cards
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
