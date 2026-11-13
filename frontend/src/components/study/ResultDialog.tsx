import { CheckCircle2, ChevronLeft, FileText, Folder, Image as ImageIcon, ScanSearch, XCircle } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select } from "@/components/ui/select";
import {
  agentErrorMessage,
  api,
  type AgendaItem,
  type FolderListing,
  type NotionPage,
  type PrintProposal,
  type Topic,
} from "@/lib/api";
import { useAgent } from "@/components/agent/AgentContext";

type Values = { total: string; first: string; wrong: string; score: string };

const num = (v: string) => (v.trim() === "" ? null : Number(v.replace(",", ".")));

/**
 * Lançar o resultado de uma prova, laboratório ou atividade (SPEC D17).
 * Pode digitar ou pedir ao agente para ler os prints (Notion ou pasta de materiais);
 * a leitura só PROPÕE os números, que você confere antes de salvar.
 */
export function ResultDialog({
  item,
  onClose,
  onSaved,
}: {
  item: AgendaItem | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [v, setV] = React.useState<Values>({
    total: "",
    first: "",
    wrong: "",
    score: "",
  });
  const [proposal, setProposal] = React.useState<PrintProposal | null>(null);
  const [error, setError] = React.useState<string>();

  React.useEffect(() => {
    setProposal(null);
    setError(undefined);
    if (!item) return;
    setV({
      total: item.total_questions?.toString() ?? "",
      first: item.first_try_correct?.toString() ?? "",
      wrong: item.wrong_attempts?.toString() ?? "",
      score: item.score?.toString() ?? "",
    });
  }, [item]);

  const set = (k: keyof Values) => (value: string) => setV((x) => ({ ...x, [k]: value }));
  const total = num(v.total);
  const first = num(v.first);
  // v1.5: simulado vale até 1,0; prova segue a regra da disciplina (ex.: 0 a 8); o resto, 0 a 10
  const maxScore = item?.max_score ?? 10;
  const digits = maxScore < 10 && item?.kind === "mock" ? 100 : 10;
  const autoScore =
    total && first !== null && first <= total ? Math.round((first / total) * maxScore * digits) / digits : null;
  const maxLabel = maxScore.toLocaleString("pt-BR", { minimumFractionDigits: maxScore < 2 ? 1 : 0 });

  const applyProposal = (p: PrintProposal) => {
    setProposal(p);
    setV({
      total: String(p.total_questions),
      first: String(p.first_try_correct),
      wrong: String(p.wrong_attempts),
      score: "",
    });
  };

  const save = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!item) return;
    if (total !== null && first !== null && first > total) return setError("Acertos de primeira maior que o total.");
    const body = {
      total_questions: total,
      first_try_correct: first,
      wrong_attempts: num(v.wrong),
      score: num(v.score) ?? autoScore,
      done: true,
    };
    try {
      await api.put(`/study/${item.type === "exam" ? "exams" : "deadlines"}/${item.id}/result`, body);
      toast.success("Resultado salvo");
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível salvar");
    }
  };

  return (
    <Dialog open={item !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent title={`Resultado · ${item?.title ?? ""}`} className="max-w-2xl">
        <div className="space-y-6">
          {item && <PrintReader item={item} onProposal={applyProposal} />}

          {proposal && <ProposalList proposal={proposal} />}

          <form onSubmit={save} className="space-y-4" noValidate>
            <div className="grid grid-cols-2 gap-4">
              <Field id="r-total" label="Questões" optional>
                {() => (
                  <Input
                    id="r-total"
                    inputMode="numeric"
                    value={v.total}
                    onChange={(e) => set("total")(e.target.value)}
                  />
                )}
              </Field>
              <Field id="r-first" label="Certas de primeira" optional>
                {() => (
                  <Input
                    id="r-first"
                    inputMode="numeric"
                    value={v.first}
                    onChange={(e) => set("first")(e.target.value)}
                  />
                )}
              </Field>
              <Field id="r-wrong" label="Tentativas erradas" optional>
                {() => (
                  <Input
                    id="r-wrong"
                    inputMode="numeric"
                    value={v.wrong}
                    onChange={(e) => set("wrong")(e.target.value)}
                  />
                )}
              </Field>
              <Field id="r-score" label={`Nota (0 a ${maxLabel})`} optional>
                {(d) => (
                  <Input
                    id="r-score"
                    inputMode="decimal"
                    aria-describedby={d}
                    placeholder={autoScore !== null ? autoScore.toLocaleString("pt-BR") : ""}
                    value={v.score}
                    onChange={(e) => set("score")(e.target.value)}
                  />
                )}
              </Field>
            </div>
            <p className="text-xs text-muted-foreground">
              Nota = certas de primeira ÷ questões × {maxLabel}. Deixe a nota vazia para usar esse cálculo, ou digite a
              nota oficial.
            </p>
            {error && (
              <p role="alert" className="text-sm text-destructive-text">
                {error}
              </p>
            )}
            <div className="flex gap-3">
              <Button variant="secondary" className="flex-1" onClick={onClose}>
                Cancelar
              </Button>
              <Button type="submit" className="flex-1">
                Salvar e marcar como feito
              </Button>
            </div>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Lista do que o modelo viu em cada print: dá para conferir antes de salvar */
function ProposalList({ proposal }: { proposal: PrintProposal }) {
  return (
    <Card className="space-y-3 p-4">
      <p className="text-sm">
        Li <b>{proposal.images}</b> print(s): <b>{proposal.total_questions}</b> questão(ões),{" "}
        <b>{proposal.first_try_correct}</b> certa(s) de primeira e <b>{proposal.wrong_attempts}</b> tentativa(s)
        errada(s).
        {proposal.unknown > 0 && ` ${proposal.unknown} print(s) não deu para ler.`} Confira e ajuste abaixo.
      </p>
      <ul className="max-h-48 space-y-1 overflow-y-auto text-xs">
        {proposal.readings.map((r, i) => (
          <li key={i} className="flex items-start gap-2">
            {r.result === "correct" ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success-text" aria-label="Certa" />
            ) : r.result === "wrong" ? (
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive-text" aria-label="Errada" />
            ) : (
              <ScanSearch className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-label="Não lida" />
            )}
            <span>
              <span className="font-medium">{r.label}</span>
              {r.question_number ? ` · questão ${r.question_number}` : ""}
              {r.note ? ` — ${r.note}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Escolher de onde ler os prints: página do Notion de um tema (por seção) ou pasta de materiais */
function PrintReader({ item, onProposal }: { item: AgendaItem; onProposal: (p: PrintProposal) => void }) {
  const { model } = useAgent();
  // O laboratório (e atividades e simulados) costuma ter página própria no caderno do Notion
  const [source, setSource] = React.useState<Source>(item.type === "deadline" ? "item" : "notion");
  const [itemPage, setItemPage] = React.useState<string | null>(item.notion_page_id ?? null);
  const [topics, setTopics] = React.useState<Topic[]>([]);
  const [topicId, setTopicId] = React.useState("");
  const [sections, setSections] = React.useState<{ section: string; images: number }[] | null>(null);
  const [section, setSection] = React.useState("");
  const [folder, setFolder] = React.useState<FolderListing | null>(null);
  const [picked, setPicked] = React.useState<string[]>([]);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string>();

  React.useEffect(() => {
    if (!item.subject_id) return;
    api
      .get<Topic[]>(`/topics?subject_id=${item.subject_id}`)
      .then((list) => setTopics(list.filter((t) => t.notion_page_id)))
      .catch(() => setTopics([]));
  }, [item.subject_id]);

  const openFolder = React.useCallback(async (path: string) => {
    setError(undefined);
    try {
      setFolder(await api.get<FolderListing>(`/prints/folder?path=${encodeURIComponent(path)}`));
      setPicked([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível abrir a pasta.");
    }
  }, []);

  React.useEffect(() => {
    if (source === "folder" && !folder) void openFolder("");
  }, [source, folder, openFolder]);

  const loadSections = async (id: string, by: "topic_id" | "deadline_id" = "topic_id") => {
    if (by === "topic_id") setTopicId(id);
    setSections(null);
    setSection("");
    setError(undefined);
    setBusy("Lendo a página do Notion…");
    try {
      setSections(await api.get(`/prints/notion-sections?${by}=${id}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível ler a página.");
    } finally {
      setBusy(null);
    }
  };

  // Página do próprio item: carrega as seções quando já está ligada
  React.useEffect(() => {
    if (source === "item" && itemPage) void loadSections(String(item.id), "deadline_id");
    if (source !== "folder") setSections(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, itemPage]);

  const linkPage = async (pageId: string) => {
    try {
      await api.put(`/study/deadlines/${item.id}/notion`, { notion_page_id: pageId });
      setItemPage(pageId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível ligar a página.");
    }
  };

  const analyze = async () => {
    setError(undefined);
    setBusy("O modelo está lendo os prints, um por um. Pode levar alguns minutos…");
    try {
      const body =
        source === "item"
          ? { source: "notion", deadline_id: item.id, section: section || null, model }
          : source === "notion"
            ? {
                source,
                topic_id: Number(topicId),
                section: section || null,
                model,
              }
            : {
                source,
                paths: picked.length ? picked : [folder?.path ?? ""],
                model,
              };
      onProposal(await api.post<PrintProposal>("/prints/analyze", body));
    } catch (err) {
      setError(agentErrorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const canAnalyze =
    busy === null &&
    (source === "item"
      ? itemPage !== null && sections !== null
      : source === "notion"
        ? topicId !== "" && sections !== null
        : folder !== null && (picked.length > 0 || folder.path !== ""));

  return (
    <section aria-labelledby="h-prints" className="space-y-3">
      <h3 id="h-prints" className="text-sm font-semibold">
        Ler dos meus prints
      </h3>
      <RadioGroup value={source} onValueChange={(x) => setSource(x as Source)} className="sm:grid-cols-3">
        {(
          [
            ...(item.type === "deadline" ? ([["item", "Página deste item no Notion"]] as const) : []),
            ["notion", "Página de um tema"],
            ["folder", "Pasta de materiais"],
          ] as const
        ).map(([value, label]) => (
          <label
            key={value}
            htmlFor={`src-${value}`}
            className="flex min-h-11 cursor-pointer items-center gap-3 sm:min-h-0"
          >
            <RadioGroupItem id={`src-${value}`} value={value} />
            <span className="text-sm">{label}</span>
          </label>
        ))}
      </RadioGroup>

      {source === "item" ? (
        itemPage ? (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Página ligada.{" "}
              <button type="button" className="text-primary-text underline" onClick={() => setItemPage(null)}>
                Trocar página
              </button>
            </p>
            {sections && <SectionSelect sections={sections} section={section} onChange={setSection} />}
          </div>
        ) : (
          <NotionPagePicker onPick={linkPage} />
        )
      ) : source === "notion" ? (
        topics.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nenhum tema desta disciplina tem página do Notion ligada. Ligue em Gerenciar › Disciplinas e temas.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="pr-topic" label="Tema (página do caderno)">
              {() => (
                <Select
                  id="pr-topic"
                  value={topicId}
                  onValueChange={loadSections}
                  placeholder="Escolha"
                  options={topics.map((t) => ({
                    value: String(t.id),
                    label: t.title,
                  }))}
                />
              )}
            </Field>
            {sections && (
              <Field id="pr-section" label="Seção da página" optional>
                {() => (
                  <Select
                    id="pr-section"
                    value={section || "all"}
                    onValueChange={(x) => setSection(x === "all" ? "" : x)}
                    options={[
                      {
                        value: "all",
                        label: `Página inteira (${sections.reduce((n, s) => n + s.images, 0)} imagens)`,
                      },
                      ...sections.map((s) => ({
                        value: s.section,
                        label: `${s.section} (${s.images})`,
                      })),
                    ]}
                  />
                )}
              </Field>
            )}
          </div>
        )
      ) : (
        folder && (
          <Card className="p-3">
            <div className="mb-2 flex items-center gap-2">
              {folder.path && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Voltar uma pasta"
                  onClick={() => openFolder(folder.path.split("/").slice(0, -1).join("/"))}
                >
                  <ChevronLeft aria-hidden="true" />
                </Button>
              )}
              <p className="truncate text-xs text-muted-foreground">{folder.path || "Pasta de materiais"}</p>
            </div>
            {folder.entries.length === 0 ? (
              <p className="text-sm text-muted-foreground">Pasta vazia ou sem imagens e PDFs.</p>
            ) : (
              <ul className="max-h-56 space-y-1 overflow-y-auto">
                {folder.entries.map((e) =>
                  e.type === "dir" ? (
                    <li key={e.path}>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="w-full justify-start"
                        onClick={() => openFolder(e.path)}
                      >
                        <Folder aria-hidden="true" />
                        {e.name}
                      </Button>
                    </li>
                  ) : (
                    <li key={e.path}>
                      <Label
                        htmlFor={`f-${e.path}`}
                        className="flex min-h-11 cursor-pointer items-center gap-3 px-3 sm:min-h-0 sm:py-1"
                      >
                        <Checkbox
                          id={`f-${e.path}`}
                          checked={picked.includes(e.path)}
                          onCheckedChange={(c) =>
                            setPicked((list) => (c === true ? [...list, e.path] : list.filter((p) => p !== e.path)))
                          }
                        />
                        {e.type === "pdf" ? (
                          <FileText className="h-4 w-4" aria-hidden="true" />
                        ) : (
                          <ImageIcon className="h-4 w-4" aria-hidden="true" />
                        )}
                        <span className="truncate text-sm font-normal">{e.name}</span>
                      </Label>
                    </li>
                  ),
                )}
              </ul>
            )}
            <p className="mt-2 text-xs text-muted-foreground">
              {picked.length > 0
                ? `${picked.length} arquivo(s) escolhido(s).`
                : folder.path
                  ? "Sem escolher arquivos, leio todas as imagens e PDFs desta pasta."
                  : "Entre na pasta da disciplina e escolha os prints."}
            </p>
          </Card>
        )
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
      <Button variant="outline" onClick={analyze} disabled={!canAnalyze}>
        <ScanSearch aria-hidden="true" />
        Ler prints e propor nota
      </Button>
    </section>
  );
}

type Source = "item" | "notion" | "folder";

function SectionSelect({
  sections,
  section,
  onChange,
}: {
  sections: { section: string; images: number }[];
  section: string;
  onChange: (s: string) => void;
}) {
  return (
    <Field id="pr-item-section" label="Seção da página" optional>
      {() => (
        <Select
          id="pr-item-section"
          value={section || "all"}
          onValueChange={(x) => onChange(x === "all" ? "" : x)}
          options={[
            { value: "all", label: `Página inteira (${sections.reduce((n, s) => n + s.images, 0)} imagens)` },
            ...sections.map((s) => ({ value: s.section, label: `${s.section} (${s.images})` })),
          ]}
        />
      )}
    </Field>
  );
}

/** Procurar a página do item entre as páginas compartilhadas com a conexão do Notion */
function NotionPagePicker({ onPick }: { onPick: (id: string) => void }) {
  const [q, setQ] = React.useState("");
  const [pages, setPages] = React.useState<NotionPage[] | null>(null);
  const [error, setError] = React.useState<string>();
  const search = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setError(undefined);
    try {
      setPages(await api.get<NotionPage[]>(`/notion/pages?q=${encodeURIComponent(q.trim())}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível buscar no Notion.");
    }
  };
  return (
    <div className="space-y-2">
      <form onSubmit={search} className="flex gap-2">
        <label htmlFor="np-q" className="sr-only">
          Nome da página no Notion
        </label>
        <Input
          id="np-q"
          placeholder="Ex.: Laboratório - Criptografia"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <Button type="submit" variant="outline">
          Buscar
        </Button>
      </form>
      {error && (
        <p role="alert" className="text-sm text-destructive-text">
          {error}
        </p>
      )}
      {pages && pages.length === 0 && <p className="text-sm text-muted-foreground">Nenhuma página encontrada.</p>}
      {pages && pages.length > 0 && (
        <ul className="max-h-48 space-y-1 overflow-y-auto">
          {pages.slice(0, 20).map((p) => (
            <li key={p.id}>
              <Button variant="ghost" size="sm" className="w-full justify-start" onClick={() => onPick(p.id)}>
                {p.title}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
