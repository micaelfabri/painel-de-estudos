import burroAnimado from "@/assets/agente/burro.webp";
import burroParado from "@/assets/agente/burro.png";
import { cn } from "@/lib/utils";

/**
 * Avatar do Burro bot (nome escolhido pelo dono em 12/11/2026). Burro animado do Noto Emoji (Google, CC BY 4.0;
 * créditos em public/CREDITOS-IMAGENS.md). Com "reduzir movimento" ligado, mostra o primeiro quadro parado.
 */
export function BurroAvatar({ className, decorative = true }: { className?: string; decorative?: boolean }) {
  return (
    <picture>
      <source media="(prefers-reduced-motion: reduce)" srcSet={burroParado} />
      <img
        src={burroAnimado}
        alt={decorative ? "" : "Burro bot"}
        aria-hidden={decorative ? true : undefined}
        width={32}
        height={32}
        className={cn("h-8 w-8 shrink-0", className)}
      />
    </picture>
  );
}
