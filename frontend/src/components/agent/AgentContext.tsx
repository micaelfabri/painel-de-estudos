import * as React from "react";

import {
  agentErrorMessage,
  api,
  type CardView,
  type ChatMessageView,
  type ModelsInfo,
  type QuestionSetView,
} from "@/lib/api";

/** Sessão de cards no painel: revisão (vencidos, um tema) ou rodada rápida com tempo e sequência */
interface CardSession {
  title: string;
  cards: CardView[];
  round?: boolean;
  key?: number;
}

interface ChatEntry {
  id: number;
  role: "user" | "agent";
  kind: "text" | "error" | "summary" | "result";
  text: string;
  /** Repetir a ação que falhou */
  retry?: () => void;
  setId?: number;
}

interface GeneratePreset {
  subjectId: number;
  topicId: number;
  attemptType: string;
  label: string;
}

interface Pending {
  label: string;
  startedAt: number;
  abort: AbortController;
}

interface AgentState {
  models: ModelsInfo | null;
  model: string | null;
  setModel: (m: string) => void;
  reloadModels: () => void;
  entries: ChatEntry[];
  pending: Pending | null;
  activeSet: QuestionSetView | null;
  /** v1.6 (D37): cards abertos no painel (revisão ou rodada rápida) */
  cardSession: CardSession | null;
  openCards: (session: CardSession) => void;
  closeCards: () => void;
  setActiveSet: (s: QuestionSetView | null) => void;
  topicId: number | null;
  setTopicId: (id: number | null) => void;
  sendChat: (message: string) => void;
  generate: (params: { topicId: number; text: string | null; nOptions: number; attemptType?: string }) => void;
  /** v1.3: inicia um conjunto por outra rota (refazer erradas, teste de foco, simulado) */
  startSet: (params: { userText: string; pendingLabel: string; path: string; body: Record<string, unknown> }) => void;
  /** Abre um conjunto já salvo (histórico) no painel do agente */
  openSet: (setId: number) => Promise<void>;
  /** Pede ao painel para abrir o formulário já preenchido (ex.: reteste do checklist) */
  preset: GeneratePreset | null;
  setPreset: (p: GeneratePreset | null) => void;
  /** Avisa as telas que dados de aprendizado mudaram (nota, retestes) */
  learningVersion: number;
  bumpLearning: () => void;
  cancel: () => void;
  pushEntry: (e: Omit<ChatEntry, "id">) => void;
  /** v1.5: apaga a conversa salva (os testes e notas continuam) */
  clearChat: () => Promise<void>;
}

const Ctx = React.createContext<AgentState | null>(null);

export function useAgent() {
  const ctx = React.useContext(Ctx);
  if (!ctx) throw new Error("useAgent fora do AgentProvider");
  return ctx;
}

let nextId = 1;

/**
 * Estado do agente fica acima do painel: abrir e fechar o painel (Sheet abaixo de lg)
 * não perde conversa nem questões (DS v2.13, painel direito).
 */
export function AgentProvider({ children }: { children: React.ReactNode }) {
  const [models, setModels] = React.useState<ModelsInfo | null>(null);
  const [model, setModel] = React.useState<string | null>(null);
  const [entries, setEntries] = React.useState<ChatEntry[]>([]);
  const [pending, setPending] = React.useState<Pending | null>(null);
  const [activeSet, setActiveSet] = React.useState<QuestionSetView | null>(null);
  const [cardSession, setCardSession] = React.useState<CardSession | null>(null);
  const openCards = React.useCallback((session: CardSession) => setCardSession({ ...session, key: Date.now() }), []);
  const closeCards = React.useCallback(() => setCardSession(null), []);
  const [topicId, setTopicId] = React.useState<number | null>(null);
  const [preset, setPreset] = React.useState<GeneratePreset | null>(null);
  const [learningVersion, setLearningVersion] = React.useState(0);
  const bumpLearning = React.useCallback(() => setLearningVersion((v) => v + 1), []);

  const reloadModels = React.useCallback(async () => {
    try {
      const info = await api.get<ModelsInfo>("/agent/models");
      setModels(info);
      setModel((current) => current ?? info.default_model ?? info.models[0] ?? null);
    } catch {
      setModels({
        base_url: "",
        reachable: false,
        models: [],
        default_model: null,
        error: "Não foi possível consultar os modelos.",
      });
    }
  }, []);

  React.useEffect(() => {
    void reloadModels();
  }, [reloadModels]);

  const pushEntry = React.useCallback((e: Omit<ChatEntry, "id">) => {
    setEntries((list) => [...list, { ...e, id: nextId++ }]);
  }, []);

  // v1.5: a conversa fica salva no servidor e volta depois de recarregar a página
  React.useEffect(() => {
    let ignore = false; // StrictMode roda o efeito duas vezes em dev
    api
      .get<ChatMessageView[]>("/agent/chat/messages")
      .then((saved) =>
        ignore
          ? undefined
          : setEntries((list) => [
              ...saved.map((m): ChatEntry => ({
                id: nextId++,
                role: m.role === "user" ? "user" : "agent",
                kind: "text",
                text: m.content,
              })),
              ...list,
            ]),
      )
      .catch(() => {});
    return () => {
      ignore = true;
    };
  }, []);

  const clearChat = React.useCallback(async () => {
    await api.del("/agent/chat/messages");
    setEntries([]);
  }, []);

  const run = React.useCallback(
    async <T,>(label: string, fn: (signal: AbortSignal) => Promise<T>, onOk: (r: T) => void, retry: () => void) => {
      const abort = new AbortController();
      setPending({ label, startedAt: Date.now(), abort });
      try {
        onOk(await fn(abort.signal));
      } catch (err) {
        if (abort.signal.aborted) {
          pushEntry({
            role: "agent",
            kind: "error",
            text: "Cancelado.",
            retry,
          });
        } else {
          pushEntry({
            role: "agent",
            kind: "error",
            text: `Não foi possível responder. ${agentErrorMessage(err)}`,
            retry,
          });
        }
      } finally {
        setPending(null);
      }
    },
    [pushEntry],
  );

  const sendChat = React.useCallback(
    (message: string) => {
      pushEntry({ role: "user", kind: "text", text: message });
      const attempt = () =>
        run(
          "Pensando…",
          (signal) =>
            api.post<{ answer: string }>(
              "/agent/chat",
              // O servidor junta as últimas mensagens salvas como contexto
              { message, topic_id: topicId, model },
              signal,
            ),
          (res) => {
            pushEntry({ role: "agent", kind: "text", text: res.answer });
          },
          attempt,
        );
      void attempt();
    },
    [model, pushEntry, run, topicId],
  );

  const generate = React.useCallback(
    ({
      topicId: tid,
      text,
      nOptions,
      attemptType = "first",
    }: {
      topicId: number;
      text: string | null;
      nOptions: number;
      attemptType?: string;
    }) => {
      pushEntry({
        role: "user",
        kind: "text",
        text: attemptType === "first" ? "Gerar as questões." : "Fazer o reteste.",
      });
      const attempt = () =>
        run(
          "Gerando resumo e questões…",
          (signal) =>
            api.post<QuestionSetView>(
              "/agent/question-sets",
              {
                topic_id: tid,
                text,
                model,
                n_options: nOptions,
                attempt_type: attemptType,
              },
              signal,
            ),
          (set) => {
            setTopicId(tid);
            setActiveSet(set);
            pushEntry({
              role: "agent",
              kind: "summary",
              setId: set.id,
              text: `Resumo de ${set.topic_title}:\n${set.summary ?? ""}\n\n${set.questions.length} questões prontas. Responda sem consultar; no fim mostro o % de acerto e o que rever.`,
            });
          },
          attempt,
        );
      void attempt();
    },
    [model, pushEntry, run],
  );

  const startSet = React.useCallback(
    ({
      userText,
      pendingLabel,
      path,
      body,
    }: {
      userText: string;
      pendingLabel: string;
      path: string;
      body: Record<string, unknown>;
    }) => {
      pushEntry({ role: "user", kind: "text", text: userText });
      const attempt = () =>
        run(
          pendingLabel,
          (signal) => api.post<QuestionSetView>(path, { model, ...body }, signal),
          (set) => {
            if (set.topic_id) setTopicId(set.topic_id);
            setActiveSet(set);
            const timer = set.time_limit_minutes ? ` Você tem ${set.time_limit_minutes} minutos.` : "";
            pushEntry({
              role: "agent",
              kind: "summary",
              setId: set.id,
              text: `${set.label ?? "Novo conjunto"} · ${set.topic_title}${set.summary ? `:\n${set.summary}` : ""}\n\n${set.questions.length} questões prontas.${timer}`,
            });
          },
          attempt,
        );
      void attempt();
    },
    [model, pushEntry, run],
  );

  const openSet = React.useCallback(async (setId: number) => {
    const set = await api.get<QuestionSetView>(`/agent/question-sets/${setId}`);
    if (set.topic_id) setTopicId(set.topic_id);
    setActiveSet(set);
  }, []);

  const cancel = React.useCallback(() => pending?.abort.abort(), [pending]);

  const value: AgentState = {
    models,
    model,
    setModel,
    reloadModels,
    entries,
    pending,
    activeSet,
    cardSession,
    openCards,
    closeCards,
    setActiveSet,
    topicId,
    setTopicId,
    sendChat,
    generate,
    startSet,
    openSet,
    cancel,
    pushEntry,
    clearChat,
    preset,
    setPreset,
    learningVersion,
    bumpLearning,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
