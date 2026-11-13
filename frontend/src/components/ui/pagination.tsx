import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";

import { Button } from "./button";

/**
 * Paginação do DS v2.13: 10 por página, controles com alvo `h-9 min-w-9` (tabela de Alvo de toque).
 * Anterior / "Página X de Y" / Próxima; nunca "carregar mais". v1.7.2: primeira e última página como botões
 * só de ícone (size icon: h-9 w-9, 44px em ponteiro grosso), com nome acessível (resposta 06 do DS).
 */
export function Pagination({
  page,
  pages,
  total,
  onPage,
  label = "Paginação",
}: {
  page: number;
  pages: number;
  total?: number;
  onPage: (page: number) => void;
  label?: string;
}) {
  if (pages <= 1) return null;
  return (
    <nav aria-label={label} className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-xs text-muted-foreground" aria-live="polite">
        Página {page} de {pages}
        {total !== undefined && ` · ${total} no total`}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="icon"
          aria-label="Primeira página"
          title="Primeira página"
          disabled={page <= 1}
          onClick={() => onPage(1)}
        >
          <ChevronsLeft aria-hidden="true" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-9 min-w-9"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft aria-hidden="true" />
          Anterior
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-9 min-w-9"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          Próxima
          <ChevronRight aria-hidden="true" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          aria-label="Última página"
          title="Última página"
          disabled={page >= pages}
          onClick={() => onPage(pages)}
        >
          <ChevronsRight aria-hidden="true" />
        </Button>
      </div>
    </nav>
  );
}
