import { ListPlus, Plus } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { CheckboxRow } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { api, type ChecklistItem, type ReviewDue } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useAgent } from "./AgentContext";

const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** Checklist do dia (DS v2.13, exceção E11): marcar conclui na hora, sem salvar */
export function DailyChecklist() {
  const { setPreset, learningVersion } = useAgent();
  const [items, setItems] = React.useState<ChecklistItem[]>([]);
  const [reviews, setReviews] = React.useState<ReviewDue[]>([]);
  const [newLabel, setNewLabel] = React.useState("");
  const [announce, setAnnounce] = React.useState("");
  const day = todayIso();

  const load = React.useCallback(async () => {
    const [list, due] = await Promise.all([
      api.get<ChecklistItem[]>(`/learning/checklist?day=${day}`),
      api.get<ReviewDue[]>(`/learning/reviews?today=${day}`),
    ]);
    setItems(list);
    setReviews(due);
  }, [day]);

  React.useEffect(() => {
    void load();
  }, [load, learningVersion]);

  const toggle = async (item: ChecklistItem, done: boolean) => {
    setItems((list) => list.map((i) => (i.id === item.id ? { ...i, done } : i)));
    setAnnounce(done ? "Concluído" : "Reaberto");
    try {
      await api.patch(`/learning/checklist/${item.id}`, { done });
    } catch {
      setItems((list) => list.map((i) => (i.id === item.id ? { ...i, done: !done } : i)));
      toast.error("Não foi possível marcar a tarefa.");
    }
  };

  const plan = async () => {
    try {
      const res = await api.post<{ added: number; items: ChecklistItem[] }>(`/learning/checklist/plan?day=${day}`, {});
      setItems(res.items);
      toast.success(res.added === 0 ? "Nada novo para acrescentar." : `${res.added} tarefa(s) acrescentada(s).`);
    } catch {
      toast.error("Não foi possível montar o dia.");
    }
  };

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    const label = newLabel.trim();
    if (!label) return;
    try {
      const item = await api.post<ChecklistItem>("/learning/checklist", { day, label, position: items.length + 1 });
      setItems((list) => [...list, item]);
      setNewLabel("");
    } catch {
      toast.error("Não foi possível adicionar a tarefa.");
    }
  };

  const startRetest = (reviewId: number) => {
    const r = reviews.find((x) => x.id === reviewId);
    if (r) setPreset({ subjectId: r.subject_id, topicId: r.topic_id, attemptType: r.attempt_type, label: r.label });
  };

  return (
    <section aria-labelledby="h-hoje" className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 id="h-hoje" className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Hoje
        </h3>
        <Button variant="ghost" size="sm" onClick={plan}>
          <ListPlus aria-hidden="true" />
          Montar o dia
        </Button>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nenhuma tarefa. Use "Montar o dia" ou adicione abaixo.</p>
      ) : (
        <ul className="divide-y divide-border">
          {items.map((item) => {
            const reviewOpen = item.review_id !== null && reviews.some((r) => r.id === item.review_id);
            return (
              <li key={item.id} className="py-1">
                <CheckboxRow
                  id={`chk-${item.id}`}
                  checked={item.done}
                  onCheckedChange={(v) => toggle(item, v)}
                  trailing={
                    item.planned_minutes ? (
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                        {formatDuration(item.planned_minutes * 60)}
                      </span>
                    ) : undefined
                  }
                >
                  <span className={cn(item.done && "text-muted-foreground line-through")}>{item.label}</span>
                </CheckboxRow>
                {reviewOpen && !item.done && (
                  <Button variant="outline" size="sm" className="mb-2 ml-7" onClick={() => startRetest(item.review_id!)}>
                    Fazer reteste
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <div aria-live="polite" className="sr-only">
        {announce}
      </div>
      <form onSubmit={add} className="flex gap-2">
        <label htmlFor="chk-new" className="sr-only">
          Nova tarefa
        </label>
        <Input id="chk-new" placeholder="Nova tarefa" value={newLabel} onChange={(e) => setNewLabel(e.target.value)} />
        <Button type="submit" variant="outline" size="icon" aria-label="Adicionar tarefa" disabled={!newLabel.trim()}>
          <Plus aria-hidden="true" />
        </Button>
      </form>
    </section>
  );
}
