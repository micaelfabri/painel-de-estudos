import * as React from "react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, type Overview, type SettingsResponse, type Topic } from "@/lib/api";

interface NotionSection {
  title: string;
  chars: number;
  text: string;
}
import { useApi } from "@/lib/useApi";
import { useAgent } from "./AgentContext";

// Mesmo limite do backend (MAX_TEXT em agent/router.py)
const MAX_TEXT = 30_000;
const fmt = (n: number) => n.toLocaleString("pt-BR");

/** Escolher tema, colar o texto e gerar resumo + questões */
export function GenerateForm({ onDone }: { onDone: () => void }) {
  const { generate, pending, topicId, setTopicId, preset, setPreset } = useAgent();
  const overview = useApi<Overview>("/overview");
  const settings = useApi<SettingsResponse>("/settings");
  const subjects = overview.data?.subjects ?? [];

  const [subjectId, setSubjectId] = React.useState<string>("");
  const [topics, setTopics] = React.useState<Topic[]>([]);
  const [topic, setTopic] = React.useState<string>(topicId ? String(topicId) : "");
  const [text, setText] = React.useState("");
  const [nOptions, setNOptions] = React.useState<string>("");
  const [error, setError] = React.useState<string>();
  const [loadingNotion, setLoadingNotion] = React.useState(false);
  // Página do Notion dividida por módulos (títulos # e ##): dá para mandar um módulo por vez
  const [notionSections, setNotionSections] = React.useState<NotionSection[]>([]);
  const [notionWhole, setNotionWhole] = React.useState("");
  const [section, setSection] = React.useState("all");
  React.useEffect(() => {
    // Trocou de tema: as partes da página anterior não valem mais
    setNotionSections([]);
    setNotionWhole("");
    setSection("all");
  }, [topic]);

  React.useEffect(() => {
    const saved = settings.data?.values.options_per_question;
    if (saved != null && nOptions === "") setNOptions(String(saved));
  }, [settings.data, nOptions]);

  // Reteste vindo do checklist: já escolhe disciplina e tema
  React.useEffect(() => {
    if (preset) setSubjectId(String(preset.subjectId));
  }, [preset]);

  React.useEffect(() => {
    if (!subjectId) return;
    api.get<Topic[]>(`/topics?subject_id=${subjectId}`).then((list) => {
      setTopics(list);
      const wanted = preset && String(preset.subjectId) === subjectId ? list.find((t) => t.id === preset.topicId) : undefined;
      const firstPending = wanted ?? list.find((t) => !t.portal_done) ?? list[0];
      if (firstPending) setTopic(String(firstPending.id));
    });
  }, [subjectId, preset]);

  const selected = topics.find((t) => String(t.id) === topic);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected) return setError("Escolha o tema.");
    if (!text.trim() && !selected.source_text) return setError("Cole o texto do tema (só o texto; prints só de diagramas).");
    if (text.trim().length > MAX_TEXT)
      return setError(
        `O texto tem ${fmt(text.trim().length)} caracteres; o limite é ${fmt(MAX_TEXT)}. Cole uma parte por vez (ex.: um módulo).`,
      );
    if (!nOptions) return setError("Escolha quantas alternativas por questão.");
    setError(undefined);
    setTopicId(selected.id);
    const attemptType = preset && preset.topicId === selected.id ? preset.attemptType : "first";
    generate({ topicId: selected.id, text: text.trim() || null, nOptions: Number(nOptions), attemptType });
    setText("");
    setPreset(null);
    onDone();
  };

  return (
    <form onSubmit={submit} className="space-y-3" noValidate>
      {preset && (
        <p className="text-sm">
          <span className="font-medium">{preset.label.charAt(0).toUpperCase() + preset.label.slice(1)}</span>
          <span className="text-muted-foreground"> · questões novas sobre o mesmo tema</span>
        </p>
      )}
      <Field id="g-subject" label="Disciplina">
        {() => (
          <Select
            id="g-subject"
            value={subjectId}
            onValueChange={setSubjectId}
            placeholder="Escolha"
            options={subjects.map((s) => ({ value: String(s.id), label: s.name }))}
          />
        )}
      </Field>
      <Field id="g-topic" label="Tema">
        {() => (
          <Select
            id="g-topic"
            value={topic}
            onValueChange={setTopic}
            placeholder="Escolha"
            disabled={topics.length === 0}
            options={topics.map((t) => ({
              value: String(t.id),
              label: t.title + (t.portal_done ? " (concluído no portal)" : ""),
            }))}
          />
        )}
      </Field>
      <Field
        id="g-text"
        label="Texto do tema"
        optional={!!selected?.source_text}
        hint={
          (selected?.source_text ? "Já há um texto salvo para este tema; deixe vazio para usá-lo." : "Cole só o texto do conteúdo.") +
          (text ? ` ${fmt(text.trim().length)} de ${fmt(MAX_TEXT)} caracteres.` : "")
        }
      >
        {(d) => <Textarea id="g-text" rows={5} value={text} aria-describedby={d} onChange={(e) => setText(e.target.value)} />}
      </Field>
      {selected?.notion_page_id && (
        <Button
          variant="outline"
          className="w-full disabled:cursor-wait"
          disabled={loadingNotion}
          onClick={async () => {
            // F5: traz o texto da página do Notion ligada ao tema (só texto, sem imagens)
            setLoadingNotion(true);
            setError(undefined);
            try {
              const out = await api.get<{ text: string; chars: number; sections: NotionSection[] }>(
                `/notion/topics/${selected.id}/text`,
              );
              setNotionWhole(out.text);
              setNotionSections(out.sections.length > 1 ? out.sections : []);
              // Página longa demais: começa pelo primeiro módulo que cabe
              const first = out.chars > MAX_TEXT ? out.sections.findIndex((x) => x.chars <= MAX_TEXT) : -1;
              setSection(first >= 0 ? String(first) : "all");
              setText(first >= 0 ? out.sections[first].text : out.text);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Não foi possível ler o Notion.");
            } finally {
              setLoadingNotion(false);
            }
          }}
        >
          {loadingNotion ? "Lendo o Notion… (página longa pode levar 1 min)" : "Usar o texto do Notion"}
        </Button>
      )}
      {notionSections.length > 0 && (
        <Field id="g-section" label="Parte da página do Notion" hint="Mande um módulo por vez: as questões ficam mais focadas.">
          {(d) => (
            <Select
              id="g-section"
              aria-describedby={d}
              value={section}
              onValueChange={(v) => {
                setSection(v);
                setText(v === "all" ? notionWhole : notionSections[Number(v)].text);
              }}
              options={[
                { value: "all", label: `Página inteira (${fmt(notionWhole.length)} caracteres)` },
                ...notionSections.map((x, i) => ({ value: String(i), label: `${x.title} (${fmt(x.chars)})` })),
              ]}
            />
          )}
        </Field>
      )}
      <Field
        id="g-options"
        label="Alternativas por questão"
        hint="Confira numa prova ou simulado real; dá para salvar em Configurações."
      >
        {(d) => (
          <Select
            id="g-options"
            value={nOptions}
            onValueChange={setNOptions}
            placeholder="Escolha"
            aria-describedby={d}
            options={["3", "4", "5"].map((v) => ({ value: v, label: `${v} alternativas` }))}
          />
        )}
      </Field>
      {error && (
        <p role="alert" className="text-sm text-destructive-text">
          {error}
        </p>
      )}
      <Button type="submit" disabled={pending !== null} className="w-full">
        {preset ? "Gerar o reteste" : "Gerar resumo e questões"}
      </Button>
    </form>
  );
}
