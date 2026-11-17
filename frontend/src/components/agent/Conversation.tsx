import { ArrowDown, ImagePlus, Loader2, Send, Trash2, X } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { fieldClass } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { useAgent } from "./AgentContext";

/** Linha "Pensando…": segundos depois de 5 s, Cancelar depois de 10 s (DS v2.13) */
function PendingRow() {
  const { pending, cancel } = useAgent();
  const [now, setNow] = React.useState(Date.now());
  React.useEffect(() => {
    if (!pending) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [pending]);
  if (!pending) return null;
  const seconds = Math.floor((now - pending.startedAt) / 1000);
  return (
    <div className="flex max-w-[85%] flex-col gap-1">
      <span className="text-xs text-muted-foreground">Burro bot</span>
      <span className="flex items-center gap-2 text-sm">
        <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
        {pending.label}
        {seconds >= 5 && <span className="tabular-nums text-muted-foreground">{seconds} s</span>}
      </span>
      {seconds >= 10 && (
        <Button variant="outline" size="sm" className="self-start" onClick={cancel}>
          Cancelar
        </Button>
      )}
    </div>
  );
}

/** v1.5: limpar a conversa salva, com confirmação */
function ClearChat() {
  const { clearChat, pending } = useAgent();
  const [open, setOpen] = React.useState(false);
  return (
    <>
      <Button variant="ghost" size="sm" className="self-end" disabled={pending !== null} onClick={() => setOpen(true)}>
        <Trash2 aria-hidden="true" />
        Limpar conversa
      </Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Limpar a conversa?"
        note="Apaga só as mensagens da conversa com o agente. Testes, notas e erros continuam salvos."
        confirmLabel="Limpar conversa"
        destructive
        onConfirm={clearChat}
      />
    </>
  );
}

/** Lista de mensagens: role="log", rolagem automática só se o usuário já estava no fim */
export function MessageList({
  children,
  scrollRef,
}: {
  children?: React.ReactNode;
  scrollRef: React.RefObject<HTMLDivElement>;
}) {
  const { entries, pending } = useAgent();
  const atBottom = React.useRef(true);
  const [showNew, setShowNew] = React.useState(false);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    atBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    if (atBottom.current) setShowNew(false);
  };

  React.useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  });

  React.useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (atBottom.current) el.scrollTop = el.scrollHeight;
    else setShowNew(true);
  }, [entries.length, pending, scrollRef]);

  return (
    <>
      {entries.length > 0 && <ClearChat />}
      <div
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-label="Conversa"
        className="flex flex-col gap-4"
      >
        {entries.map((e) =>
          e.role === "user" ? (
            <div
              key={e.id}
              className="max-w-[85%] self-end whitespace-pre-wrap rounded-xl bg-accent px-3 py-2 text-sm text-accent-foreground"
            >
              {e.images && (
                <div className="mb-2 flex flex-wrap gap-2">
                  {e.images.map((src, i) => (
                    <img
                      key={i}
                      src={src}
                      alt={`Imagem ${i + 1} enviada`}
                      className="h-20 w-20 rounded-md border border-border object-cover"
                    />
                  ))}
                </div>
              )}
              {e.text}
            </div>
          ) : (
            <div key={e.id} className="flex max-w-[85%] flex-col gap-1">
              <span className="text-xs text-muted-foreground">Burro bot</span>
              <span
                className={cn(
                  "whitespace-pre-wrap text-sm",
                  e.kind === "error" ? "text-destructive-text" : "text-foreground",
                )}
              >
                {e.text}
              </span>
              {e.kind === "error" && e.retry && (
                <Button variant="outline" size="sm" className="self-start" onClick={e.retry}>
                  Tentar de novo
                </Button>
              )}
            </div>
          ),
        )}
        <PendingRow />
      </div>
      {children}
      {showNew && (
        <Button
          variant="secondary"
          size="sm"
          className="sticky bottom-2 self-center"
          onClick={() => {
            const el = scrollRef.current;
            if (el) el.scrollTop = el.scrollHeight;
            setShowNew(false);
          }}
        >
          <ArrowDown aria-hidden="true" />
          Novas mensagens
        </Button>
      )}
    </>
  );
}

/** Entrada: Textarea até 6 linhas, Enter envia, Shift+Enter quebra linha */
const MAX_IMAGES = 3;
const MAX_BYTES = 8 * 1024 * 1024;
const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];

function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export function ChatInput() {
  const { sendChat, pending } = useAgent();
  const [value, setValue] = React.useState("");
  // v1.10 (D52): prints por anexo ou colados com Ctrl+V; vão só ao modelo local
  const [images, setImages] = React.useState<string[]>([]);
  const ref = React.useRef<HTMLTextAreaElement>(null);
  const fileRef = React.useRef<HTMLInputElement>(null);

  React.useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    const line = parseFloat(getComputedStyle(el).lineHeight) || 21;
    el.style.height = `${Math.min(el.scrollHeight, line * 6 + 16)}px`;
  }, [value]);

  const addFiles = async (files: File[]) => {
    const ok = files.filter((f) => IMAGE_TYPES.includes(f.type));
    if (ok.length < files.length) toast.error("Só dá para mandar imagens (PNG, JPG, WebP ou GIF).");
    const small = ok.filter((f) => f.size <= MAX_BYTES);
    if (small.length < ok.length) toast.error("Imagem grande demais (máximo 8 MB).");
    const room = MAX_IMAGES - images.length;
    if (small.length > room) toast.error(`No máximo ${MAX_IMAGES} imagens por mensagem.`);
    const urls = await Promise.all(small.slice(0, Math.max(room, 0)).map(readAsDataUrl));
    if (urls.length) setImages((list) => [...list, ...urls].slice(0, MAX_IMAGES));
  };

  const send = () => {
    const text = value.trim() || (images.length ? "Veja a imagem." : "");
    if (!text || pending) return;
    sendChat(text, images);
    setValue("");
    setImages([]);
  };

  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
    >
      {images.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Imagens para enviar">
          {images.map((src, i) => (
            <li key={i} className="relative">
              <img
                src={src}
                alt={`Imagem ${i + 1} para enviar`}
                className="h-16 w-16 rounded-md border border-border object-cover"
              />
              <Button
                type="button"
                variant="secondary"
                size="icon"
                className="absolute -right-2 -top-2 h-6 w-6 rounded-full sm:h-6 sm:w-6"
                aria-label={`Remover imagem ${i + 1}`}
                onClick={() => setImages((list) => list.filter((_, j) => j !== i))}
              >
                <X aria-hidden="true" />
              </Button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex items-end gap-2">
        <input
          ref={fileRef}
          type="file"
          accept={IMAGE_TYPES.join(",")}
          multiple
          className="sr-only"
          tabIndex={-1}
          aria-hidden="true"
          onChange={(e) => {
            void addFiles(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          aria-label="Anexar imagem"
          title="Anexar imagem (ou cole com Ctrl+V)"
          disabled={images.length >= MAX_IMAGES || pending !== null}
          onClick={() => fileRef.current?.click()}
        >
          <ImagePlus aria-hidden="true" />
        </Button>
        <label htmlFor="agent-input" className="sr-only">
          Mensagem para o agente
        </label>
        <textarea
          id="agent-input"
          ref={ref}
          rows={1}
          value={value}
          placeholder="Pergunte algo sobre o tema…"
          onChange={(e) => setValue(e.target.value)}
          onPaste={(e) => {
            const files = Array.from(e.clipboardData.files).filter((f) => f.type.startsWith("image/"));
            if (files.length) {
              e.preventDefault();
              void addFiles(files);
            }
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          className={cn(fieldClass, "h-auto min-h-11 resize-none sm:h-auto sm:min-h-9")}
        />
        <Button
          type="submit"
          size="icon"
          aria-label="Enviar"
          disabled={(!value.trim() && images.length === 0) || pending !== null}
        >
          <Send aria-hidden="true" />
        </Button>
      </div>
    </form>
  );
}
