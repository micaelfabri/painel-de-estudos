import * as DialogPrimitive from "@radix-ui/react-dialog";
import { AlertTriangle, Bot, RotateCcw, Sparkles, Timer, X } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { SheetContent } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useAgent } from "./AgentContext";
import { ChatInput, MessageList } from "./Conversation";
import { DailyChecklist } from "./DailyChecklist";
import { GenerateForm } from "./GenerateForm";
import { QuestionFlow } from "./QuestionFlow";
import { ReviewMistakes } from "./ReviewMistakes";

function ModelStatus() {
  const { models, model, setModel, reloadModels } = useAgent();
  if (!models) return <p className="text-xs text-muted-foreground">Consultando o modelo local…</p>;
  if (!models.reachable || models.models.length === 0) {
    // Servidor no ar mas sem modelos (ex.: Ollama sem nada baixado) também bloqueia o agente
    const message = models.reachable
      ? `Nenhum modelo em ${models.base_url}. Baixe um modelo nesse app ou troque o endereço em Gerenciar › Configurações.`
      : `${models.error ?? "Modelo local fora do ar."} Abra o Ollama (ou o LM Studio) e tente de novo.`;
    return (
      <div className="space-y-2">
        <p className="flex items-start gap-2 text-xs text-warning-text">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{message}</span>
        </p>
        <Button variant="outline" size="sm" onClick={reloadModels}>
          Tentar de novo
        </Button>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <Label htmlFor="agent-model">Modelo</Label>
      <Select
        id="agent-model"
        value={model ?? ""}
        onValueChange={setModel}
        placeholder="Escolha um modelo"
        options={models.models.map((m) => ({ value: m, label: m === models.default_model ? `${m} (padrão)` : m }))}
      />
    </div>
  );
}

/** Conteúdo do painel do agente (igual na coluna lg e no Sheet) */
function AgentPanelBody({ onClose }: { onClose?: () => void }) {
  const { activeSet, preset, bumpLearning } = useAgent();
  const [showForm, setShowForm] = React.useState(false);
  const [reviewing, setReviewing] = React.useState(false);

  // Reteste pedido pelo checklist abre o formulário já preenchido
  React.useEffect(() => {
    if (preset) {
      setReviewing(false);
      setShowForm(true);
    }
  }, [preset]);
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const showQuestions = activeSet !== null && !showForm;

  const goToTimer = () => {
    onClose?.();
    const el = document.getElementById("cronometro");
    el?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "center",
    });
    el?.querySelector<HTMLButtonElement>("button")?.focus();
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2 border-b border-border p-4">
        <Bot className="h-5 w-5 text-primary-text" aria-hidden="true" />
        <h2 className="flex-1 text-base font-semibold">Agente de estudos</h2>
        {onClose && (
          <Button variant="ghost" size="icon" aria-label="Fechar agente" onClick={onClose}>
            <X aria-hidden="true" />
          </Button>
        )}
      </div>

      <div ref={scrollRef} className="relative flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
        <ModelStatus />
        <div className="flex flex-wrap gap-2">
          <Button
            variant={showForm ? "secondary" : "outline"}
            size="sm"
            onClick={() => setShowForm((v) => !v)}
            aria-expanded={showForm}
          >
            <Sparkles aria-hidden="true" />
            Gerar questões
          </Button>
          <Button
            variant={reviewing ? "secondary" : "outline"}
            size="sm"
            onClick={() => setReviewing((v) => !v)}
            aria-expanded={reviewing}
          >
            <RotateCcw aria-hidden="true" />
            Revisar erros
          </Button>
          <Button variant="outline" size="sm" onClick={goToTimer}>
            <Timer aria-hidden="true" />
            Cronometrar
          </Button>
        </div>
        <DailyChecklist />
        {showForm && <GenerateForm onDone={() => setShowForm(false)} />}
        {reviewing ? (
          <ReviewMistakes onClose={() => setReviewing(false)} />
        ) : (
          <MessageList scrollRef={scrollRef}>{showQuestions && <QuestionFlow onFinished={bumpLearning} />}</MessageList>
        )}
      </div>

      <div className="border-t border-border p-4">
        <ChatInput />
      </div>
    </div>
  );
}

/** Painel direito a partir de lg: terceira coluna, altura da linha, rolagem própria (DS v2.13) */
export function AgentAside() {
  return (
    <aside
      role="complementary"
      aria-label="Agente de estudos"
      className="hidden w-80 shrink-0 border-l border-border bg-card lg:flex lg:flex-col xl:w-96"
    >
      <AgentPanelBody />
    </aside>
  );
}

/** Abaixo de lg: botão só de ícone na topbar abre o painel como Sheet à direita */
export function AgentSheetTrigger() {
  const [open, setOpen] = React.useState(false);
  return (
    <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
      <DialogPrimitive.Trigger asChild>
        <Button variant="ghost" size="icon" aria-label="Abrir agente" className="lg:hidden">
          <Bot aria-hidden="true" />
        </Button>
      </DialogPrimitive.Trigger>
      <SheetContent side="right" title="Agente de estudos" className="xl:w-96">
        <AgentPanelBody onClose={() => setOpen(false)} />
      </SheetContent>
    </DialogPrimitive.Root>
  );
}
