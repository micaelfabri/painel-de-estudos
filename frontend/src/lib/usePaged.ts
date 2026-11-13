import * as React from "react";

/** DS v2.13: listas longas paginadas com 10 por página (nunca "carregar mais") */
export const PER_PAGE = 10;

/**
 * v1.7.2: paginação no navegador para listas que já chegam inteiras da API.
 * Volta para a página 1 quando `resetKey` muda (ex.: filtro) e não passa da última página quando a lista
 * encolhe. Ao trocar de página, o foco vai para o início da lista (`anchor`, com tabIndex -1), como pede a
 * resposta 06 do DS, e a tela vai junto, sem animação.
 */
export function usePaged<T>(rows: T[], resetKey: unknown = null, perPage = PER_PAGE) {
  const [page, setPage] = React.useState(1);
  const anchor = React.useRef<HTMLElement | null>(null);
  const pages = Math.max(1, Math.ceil(rows.length / perPage));

  React.useEffect(() => setPage(1), [resetKey]);
  const current = Math.min(page, pages);

  const goTo = React.useCallback((p: number) => {
    setPage(p);
    // Depois de renderizar a página nova
    requestAnimationFrame(() => {
      anchor.current?.focus({ preventScroll: true });
      anchor.current?.scrollIntoView?.({ block: "start" });
    });
  }, []);

  return {
    page: current,
    pages,
    total: rows.length,
    slice: rows.slice((current - 1) * perPage, current * perPage),
    goTo,
    anchor,
  };
}
