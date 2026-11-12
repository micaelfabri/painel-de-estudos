import * as React from "react";
import { useLocation } from "react-router-dom";
import { Toaster } from "sonner";

// Resposta do DS ao pedido 02 (provisória até a próxima versão do DS):
// com o painel direito aberto (lg+), o toast sai de cima da conversa e fica no canto do conteúdo principal.
// Deslocamento = largura do painel + margem de 16px: 320 + 16 em lg, 384 + 16 em xl.
const OFFSET = { lg: 336, xl: 400 };

function useMedia(query: string): boolean {
  const [match, setMatch] = React.useState(() => window.matchMedia(query).matches);
  React.useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatch(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return match;
}

/** Toast no canto inferior direito, com botão de fechar (DS). */
export function AppToaster() {
  const panelOpen = !useLocation().pathname.startsWith("/gerenciar"); // o agente só aparece no modo Estudo
  const lg = useMedia("(min-width: 1024px)");
  const xl = useMedia("(min-width: 1280px)");
  const right = panelOpen && lg ? (xl ? OFFSET.xl : OFFSET.lg) : undefined;
  return (
    <Toaster
      position="bottom-right"
      closeButton
      visibleToasts={3}
      offset={right ? { right } : undefined}
    />
  );
}
