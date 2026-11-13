import * as AlertDialogPrimitive from "@radix-ui/react-alert-dialog";
import { AlertCircle, Info } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";
import { Button } from "./button";

/**
 * Confirmação (AlertDialog do DS v2.13; resposta 03 do DS): centralizada, max-w-lg, botões `flex gap-3`
 * com `flex-1`. O AlertDialog do Radix não fecha ao clicar fora, Esc conta como Cancelar e o foco
 * começa no Cancelar. `note` = aviso do efeito da ação (bloco role="note" bg-muted/50 com Info),
 * ligado ao aria-describedby. Se a ação falhar, fica aberto com o bloco de erro e "Nada foi alterado.".
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  note,
  confirmLabel,
  cancelLabel = "Cancelar",
  destructive = false,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  note?: React.ReactNode;
  confirmLabel: string;
  /** Texto do botão que fecha sem fazer nada (padrão "Cancelar") */
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => Promise<void> | void;
}) {
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Resposta 06 do DS: ao fechar, o foco volta para quem abriu (o diálogo não tem gatilho próprio)
  const opener = React.useRef<HTMLElement | null>(null);
  React.useEffect(() => {
    if (open) {
      setError(null);
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    }
  }, [open]);

  const confirm = async (ev: React.MouseEvent) => {
    // O Action do Radix fecharia na hora; fecha só depois de dar certo
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível concluir.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <AlertDialogPrimitive.Root open={open} onOpenChange={(v) => !busy && onOpenChange(v)}>
      <AlertDialogPrimitive.Portal>
        <AlertDialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm" />
        <AlertDialogPrimitive.Content
          onCloseAutoFocus={(e) => {
            const el = opener.current;
            if (el && el.isConnected) {
              e.preventDefault();
              el.focus();
            }
          }}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100%-32px)] max-w-lg -translate-x-1/2 -translate-y-1/2",
            "space-y-4 overflow-y-auto rounded-xl border border-border bg-card p-6 shadow-lg",
          )}
        >
          <AlertDialogPrimitive.Title className="text-base font-semibold">{title}</AlertDialogPrimitive.Title>
          {note ? (
            <AlertDialogPrimitive.Description asChild>
              <div role="note" className="flex items-start gap-2 rounded-md border bg-muted/50 p-3">
                <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <div className="text-sm text-foreground">{note}</div>
              </div>
            </AlertDialogPrimitive.Description>
          ) : (
            <AlertDialogPrimitive.Description className="sr-only">{title}</AlertDialogPrimitive.Description>
          )}
          {error && (
            <div role="alert" className="rounded-md border border-destructive bg-destructive/10 p-3">
              <p className="flex items-center gap-2 text-sm font-medium text-destructive-text">
                <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
                {error}
              </p>
              <p className="text-sm text-foreground">Nada foi alterado.</p>
            </div>
          )}
          <div className="flex gap-3">
            <AlertDialogPrimitive.Cancel asChild>
              <Button variant="secondary" className="flex-1" disabled={busy}>
                {cancelLabel}
              </Button>
            </AlertDialogPrimitive.Cancel>
            <AlertDialogPrimitive.Action asChild>
              <Button
                className="flex-1"
                variant={destructive ? "destructive" : "default"}
                onClick={confirm}
                disabled={busy}
              >
                {confirmLabel}
              </Button>
            </AlertDialogPrimitive.Action>
          </div>
        </AlertDialogPrimitive.Content>
      </AlertDialogPrimitive.Portal>
    </AlertDialogPrimitive.Root>
  );
}
