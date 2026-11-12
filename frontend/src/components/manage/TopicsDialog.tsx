import { Plus } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { api, type NotionPage, type Subject, type Topic } from "@/lib/api";

const NO_PAGE = "none";

interface Draft {
  id: number | null;
  title: string;
  portal_done: boolean;
  notion_page_id: string | null;
  original?: Topic;
}

/** Temas da disciplina: título, "concluído no portal" e página do Notion (F5). Grava tudo em Salvar. */
export function TopicsDialog({
  subject,
  onOpenChange,
  onSaved,
}: {
  subject: Subject | null;
  onOpenChange: (o: boolean) => void;
  onSaved: () => void;
}) {
  const [drafts, setDrafts] = React.useState<Draft[]>([]);
  const [saving, setSaving] = React.useState(false);
  // Páginas compartilhadas com a conexão do Notion; vazio = Notion não configurado (campo some)
  const [pages, setPages] = React.useState<NotionPage[]>([]);
  const lastInput = React.useRef<HTMLInputElement>(null);
  const focusNew = React.useRef(false);

  React.useEffect(() => {
    if (!subject) return;
    api
      .get<Topic[]>(`/topics?subject_id=${subject.id}`)
      .then((topics) =>
        setDrafts(
          topics.map((t) => ({ id: t.id, title: t.title, portal_done: t.portal_done, notion_page_id: t.notion_page_id, original: t })),
        ),
      );
    api
      .get<NotionPage[]>("/notion/pages")
      .then(setPages)
      .catch(() => setPages([]));
  }, [subject]);

  React.useEffect(() => {
    if (focusNew.current) {
      lastInput.current?.focus();
      focusNew.current = false;
    }
  }, [drafts.length]);

  const update = (idx: number, patch: Partial<Draft>) => setDrafts((d) => d.map((x, i) => (i === idx ? { ...x, ...patch } : x)));

  const add = () => {
    focusNew.current = true;
    setDrafts((d) => [...d, { id: null, title: `Tema ${d.length + 1}`, portal_done: false, notion_page_id: null }]);
  };

  const save = async () => {
    if (!subject) return;
    setSaving(true);
    try {
      for (const [idx, d] of drafts.entries()) {
        const title = d.title.trim() || `Tema ${idx + 1}`;
        if (d.id === null) {
          await api.post("/topics", {
            subject_id: subject.id,
            position: idx + 1,
            title,
            portal_done: d.portal_done,
            notion_page_id: d.notion_page_id,
          });
        } else if (
          d.original &&
          (d.original.title !== title ||
            d.original.portal_done !== d.portal_done ||
            d.original.notion_page_id !== d.notion_page_id)
        ) {
          await api.put(`/topics/${d.id}`, { ...d.original, title, portal_done: d.portal_done, notion_page_id: d.notion_page_id });
        }
      }
      toast.success("Temas salvos");
      onSaved();
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Não foi possível salvar os temas");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={subject !== null} onOpenChange={onOpenChange}>
      <DialogContent title={`Temas · ${subject?.name ?? ""}`} description="Marque os conteúdos já concluídos no portal e, se quiser, ligue cada tema à página dele no Notion.">
        <ol className="space-y-3">
          {drafts.map((d, idx) => (
            <li key={d.id ?? `novo-${idx}`} className="flex flex-col gap-2 sm:flex-row sm:items-center">
              <label htmlFor={`t-title-${idx}`} className="sr-only">
                Título do tema {idx + 1}
              </label>
              <Input
                id={`t-title-${idx}`}
                ref={idx === drafts.length - 1 ? lastInput : undefined}
                value={d.title}
                onChange={(e) => update(idx, { title: e.target.value })}
              />
              {pages.length > 0 && (
                <>
                  <label htmlFor={`t-notion-${idx}`} className="sr-only">
                    Página do Notion do tema {idx + 1}
                  </label>
                  <Select
                    id={`t-notion-${idx}`}
                    className="sm:w-56 sm:shrink-0"
                    value={d.notion_page_id ?? NO_PAGE}
                    onValueChange={(v) => update(idx, { notion_page_id: v === NO_PAGE ? null : v })}
                    options={[
                      { value: NO_PAGE, label: "Sem página do Notion" },
                      ...pages.map((p) => ({ value: p.id, label: p.title })),
                    ]}
                  />
                </>
              )}
              <label
                htmlFor={`t-done-${idx}`}
                className="flex min-h-11 shrink-0 cursor-pointer items-center gap-2 text-sm sm:min-h-0"
              >
                <Checkbox
                  id={`t-done-${idx}`}
                  checked={d.portal_done}
                  onCheckedChange={(v) => update(idx, { portal_done: v === true })}
                />
                Concluído no portal
              </label>
            </li>
          ))}
        </ol>
        <Button variant="outline" className="mt-4" onClick={add}>
          <Plus aria-hidden="true" />
          Adicionar tema
        </Button>
        <div className="mt-6 flex gap-3">
          <Button variant="secondary" className="flex-1" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button className="flex-1 disabled:cursor-wait" onClick={save} disabled={saving}>
            Salvar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
