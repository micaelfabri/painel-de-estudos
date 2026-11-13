import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";
import { Button } from "./button";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

const overlay = "fixed inset-0 z-50 bg-black/50 backdrop-blur-sm";

/** Modal centralizado: rounded-xl, max-w-lg, max-h-[90vh] com rolagem */
export function DialogContent({
  title,
  description,
  children,
  className,
  onCloseAutoFocus,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  /** Para onde vai o foco ao fechar (ex.: a lista, depois de excluir o item que abriu o modal) */
  onCloseAutoFocus?: (event: Event) => void;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className={overlay} />
      <DialogPrimitive.Content
        onCloseAutoFocus={onCloseAutoFocus}
        className={cn(
          "fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[calc(100%-32px)] max-w-lg -translate-x-1/2 -translate-y-1/2",
          "overflow-y-auto rounded-xl border border-border bg-card p-6 shadow-lg",
          className,
        )}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <DialogPrimitive.Title className="text-base font-semibold">{title}</DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="mt-1 text-sm text-muted-foreground">
                {description}
              </DialogPrimitive.Description>
            ) : (
              <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
            )}
          </div>
          <DialogPrimitive.Close asChild>
            <Button variant="ghost" size="icon" aria-label="Fechar">
              <X aria-hidden="true" />
            </Button>
          </DialogPrimitive.Close>
        </div>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

/** Sheet lateral (painel do agente abaixo de lg, menu da sidebar no celular) */
export function SheetContent({
  side,
  title,
  children,
  className,
}: {
  side: "left" | "right";
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className={overlay} />
      <DialogPrimitive.Content
        className={cn(
          "fixed inset-y-0 z-50 flex h-[100dvh] w-80 max-w-full flex-col bg-card shadow-lg",
          side === "right" ? "right-0 border-l" : "left-0 border-r",
          "max-sm:inset-0 max-sm:w-full max-sm:border-0",
          className,
        )}
      >
        <DialogPrimitive.Title className="sr-only">{title}</DialogPrimitive.Title>
        <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
