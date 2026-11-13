import * as DialogPrimitive from "@radix-ui/react-dialog";
import { AlertTriangle, Layers, RotateCcw, Sparkles, Timer, X } from "lucide-react";
import * as React from "react";

import { CardSessionView, startDue } from "@/components/cards/CardSessionView";
import { Button } from "@/components/ui/button";
import { SheetContent } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useAgent } from "./AgentContext";
import { BurroAvatar } from "./BurroAvatar";
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
        options={models.models.map((m) => ({
          value: m,
          label: m === models.default_model ? `${m} (padrão)` : m,
        }))}
      />
    </div>
  );
}

/** Conteúdo do painel do agente (igual na coluna lg e no Sheet) */
function AgentPanelBody({ onClose }: { onClose?: () => void }) {
  const { activeSet, preset, bumpLearning, cardSession, openCards, closeCards } = useAgent();
  const [showForm, setShowForm] = React.useState(false);
  const [reviewing, setReviewing] = React.useState(false);

  // Reteste pedido pelo checklist abre o formulário já preenchido
  React.useEffect(() => {
    if (preset) {
      setReviewing(false);
      setShowForm(true);
    }
  }, [preset]);
  // Conjunto aberto pelo histórico ou por refazer/simulado: mostra as questões
  React.useEffect(() => {
    if (activeSet) {
      setReviewing(false);
      setShowForm(false);
      closeCards();
    }
  }, [activeSet?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  // v1.6: cards abertos (botão, página Cards ou rodada rápida) ocupam o lugar da conversa
  React.useEffect(() => {
    if (cardSession) {
      setReviewing(false);
      setShowForm(false);
    }
  }, [cardSession?.key]); // eslint-disable-line react-hooks/exhaustive-deps
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
        <BurroAvatar />
        <h2 className="flex-1 text-base font-semibold">
          Burro bot <span className="text-xs font-normal text-muted-foreground">agente de estudos</span>
        </h2>
        {onClose && (
          <Button variant="ghost" size="icon" aria-label="Fechar o Burro bot" onClick={onClose}>
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
            onClick={() => {
              closeCards();
              setReviewing((v) => !v);
            }}
            aria-expanded={reviewing}
          >
            <RotateCcw aria-hidden="true" />
            Revisar erros
          </Button>
          <Button
            variant={cardSession ? "secondary" : "outline"}
            size="sm"
            onClick={() => (cardSession ? closeCards() : void startDue(openCards))}
            aria-expanded={cardSession !== null}
          >
            <Layers aria-hidden="true" />
            Cards
          </Button>
          <Button variant="outline" size="sm" onClick={goToTimer}>
            <Timer aria-hidden="true" />
            Cronometrar
          </Button>
        </div>
        <DailyChecklist />
        {showForm && <GenerateForm onDone={() => setShowForm(false)} />}
        {cardSession ? (
          <CardSessionView key={cardSession.key} />
        ) : reviewing ? (
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
      aria-label="Burro bot, agente de estudos"
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
        <Button variant="ghost" size="icon" aria-label="Abrir o Burro bot" className="lg:hidden">
          <BurroAvatar className="h-6 w-6" />
        </Button>
      </DialogPrimitive.Trigger>
      <SheetContent side="right" title="Burro bot, agente de estudos" className="xl:w-96">
        <AgentPanelBody onClose={() => setOpen(false)} />
      </SheetContent>
    </DialogPrimitive.Root>
  );
}
