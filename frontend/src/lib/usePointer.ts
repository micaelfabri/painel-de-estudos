import * as React from "react";

const QUERY = "(pointer: coarse)";

/** Ponteiro grosso (toque). Resposta 04 do DS: no toque, as barras do gráfico de horas viram só visual. */
export function useCoarsePointer() {
  const get = () => typeof window !== "undefined" && !!window.matchMedia?.(QUERY).matches;
  const [coarse, setCoarse] = React.useState(get);
  React.useEffect(() => {
    const mq = window.matchMedia?.(QUERY);
    if (!mq) return;
    const on = () => setCoarse(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return coarse;
}
