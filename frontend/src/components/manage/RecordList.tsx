import * as React from "react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface Column<T> {
  header: string;
  cell: (row: T) => React.ReactNode;
  numeric?: boolean;
  /** Mostrado no cartão (abaixo de md); no máximo três campos secundários */
  inCard?: boolean;
}

interface RecordListProps<T> {
  rows: T[];
  rowKey: (row: T) => string | number;
  title: (row: T) => React.ReactNode;
  columns: Column<T>[];
  actions: (row: T) => React.ReactNode;
  empty: string;
  caption: string;
}

/**
 * Lista de registros (DS): tabela a partir de md, cartões abaixo de md, mesma fonte de dados.
 * Ações visíveis em cada linha/cartão (sem gesto de deslizar).
 */
export function RecordList<T>({ rows, rowKey, title, columns, actions, empty, caption }: RecordListProps<T>) {
  if (rows.length === 0) {
    return (
      <Card className="p-6">
        <p className="text-sm text-muted-foreground">{empty}</p>
      </Card>
    );
  }
  const cardColumns = columns.filter((c) => c.inCard).slice(0, 3);
  return (
    <>
      <Card className="hidden overflow-x-auto md:block">
        <table className="w-full text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="bg-muted/50">
            <tr>
              <th scope="col" className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Nome
              </th>
              {columns.map((c) => (
                <th
                  key={c.header}
                  scope="col"
                  className={cn(
                    "px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground",
                    c.numeric ? "text-right" : "text-left",
                  )}
                >
                  {c.header}
                </th>
              ))}
              <th scope="col" className="px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                <span className="sr-only">Ações</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={rowKey(row)} className="border-t border-border transition-colors duration-200 hover:bg-muted/50">
                <td className="px-3 py-2 font-medium">{title(row)}</td>
                {columns.map((c) => (
                  <td key={c.header} className={cn("px-3 py-2", c.numeric && "text-right tabular-nums")}>
                    {c.cell(row)}
                  </td>
                ))}
                <td className="px-3 py-2">
                  <div className="flex justify-end gap-2">{actions(row)}</div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <ul className="grid gap-3 md:hidden" aria-label={caption}>
        {rows.map((row) => (
          <li key={rowKey(row)} className="rounded-xl border border-border bg-card p-4">
            <p className="font-medium line-clamp-2">{title(row)}</p>
            <dl className="mt-2 space-y-1">
              {cardColumns.map((c) => (
                <div key={c.header} className="flex justify-between gap-2 text-xs">
                  <dt className="text-muted-foreground">{c.header}</dt>
                  <dd className={cn(c.numeric && "tabular-nums")}>{c.cell(row)}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-3 flex flex-wrap gap-2">{actions(row)}</div>
          </li>
        ))}
      </ul>
    </>
  );
}
