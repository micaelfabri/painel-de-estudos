import * as React from "react";

import { cn } from "@/lib/utils";
import { focusRing } from "./button";

export const fieldClass = cn(
  "flex h-11 w-full rounded-md border border-input bg-input-background px-3 py-2 text-sm sm:h-9",
  "placeholder:text-muted-foreground disabled:pointer-events-none disabled:opacity-50",
  "aria-[invalid=true]:border-destructive",
  focusRing,
);

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => <input ref={ref} className={cn(fieldClass, className)} {...props} />,
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea ref={ref} className={cn(fieldClass, "h-auto min-h-[96px] sm:h-auto", className)} {...props} />
  ),
);
Textarea.displayName = "Textarea";
