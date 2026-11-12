import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";
import { focusRing } from "./button";

// Checkbox no tamanho do primitivo (16px). Com rótulo, o alvo é a linha inteira (CheckboxRow).
export const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      "peer h-4 w-4 shrink-0 cursor-pointer rounded-sm border border-input bg-input-background",
      "data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground",
      "disabled:cursor-not-allowed disabled:opacity-50",
      focusRing,
      className,
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator className="flex items-center justify-center">
      <Check className="h-3 w-3" aria-hidden="true" />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
));
Checkbox.displayName = "Checkbox";

interface CheckboxRowProps {
  id: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  children: React.ReactNode;
  trailing?: React.ReactNode;
  className?: string;
}

/** Linha de Checkbox: o <label> inteiro é o alvo, min-h-11 abaixo de sm (DS v2.7) */
export function CheckboxRow({ id, checked, onCheckedChange, children, trailing, className }: CheckboxRowProps) {
  return (
    <label htmlFor={id} className={cn("flex min-h-11 cursor-pointer items-center gap-3 py-2 sm:min-h-0", className)}>
      <Checkbox id={id} checked={checked} onCheckedChange={(v) => onCheckedChange(v === true)} />
      <span className="flex-1 text-sm">{children}</span>
      {trailing}
    </label>
  );
}
