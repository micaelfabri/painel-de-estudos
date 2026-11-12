import { cn } from "@/lib/utils";

export function Separator({ className }: { className?: string }) {
  return <div role="separator" className={cn("my-6 h-px bg-border", className)} />;
}
