import * as React from "react";

import { api } from "./api";

/** Busca simples com recarga manual. Sem cache global: o app é local e pequeno. */
export function useApi<T>(path: string | null) {
  const [data, setData] = React.useState<T | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(path !== null);

  const reload = React.useCallback(async () => {
    if (path === null) return;
    setLoading(true);
    try {
      setData(await api.get<T>(path));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  }, [path]);

  React.useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}
