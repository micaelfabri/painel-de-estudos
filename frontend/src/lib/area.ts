import { useLocation } from "react-router-dom";

import type { Area, CourseModuleOption, Degree, Overview, Subject } from "@/lib/api";
import { useApi } from "@/lib/useApi";

/** v1.8 (D38): a área da página aberta — faculdade ou cursos */
export function areaFromPath(pathname: string): Area {
  return pathname.startsWith("/cursos") ? "cursos" : "faculdade";
}

export function useArea(): Area {
  return areaFromPath(useLocation().pathname);
}

/** Textos que mudam com a área (títulos das páginas reaproveitadas) */
export const AREA_TEXT: Record<Area, { subject: string; allSubjects: string; scope: string }> = {
  faculdade: { subject: "Disciplina", allSubjects: "Todas as disciplinas", scope: "da faculdade" },
  cursos: { subject: "Módulo", allSubjects: "Todos os cursos", scope: "dos cursos" },
};

/**
 * Disciplinas para os filtros: na faculdade, as do semestre atual; nos cursos, os módulos dos cursos em
 * andamento, com o nome do curso na frente.
 */
export function useAreaSubjects(area: Area): { id: number; name: string }[] {
  const overview = useApi<Overview>(area === "faculdade" ? "/overview" : null);
  const modules = useApi<CourseModuleOption[]>(area === "cursos" ? "/courses/modules" : null);
  if (area === "faculdade") return (overview.data?.subjects ?? []).map((s) => ({ id: s.id, name: s.name }));
  return (modules.data ?? []).map((m) => ({ id: m.id, name: `${m.course_name} · ${m.name}` }));
}

/** Disciplinas só da faculdade (D38/D42): os módulos dos cursos não entram em provas e prazos */
export function useCollegeSubjects(): Subject[] {
  const degrees = useApi<Degree[]>("/degrees");
  const subjects = useApi<Subject[]>("/subjects");
  const ids = new Set((degrees.data ?? []).filter((d) => d.kind === "degree").map((d) => d.id));
  return (subjects.data ?? []).filter((s) => ids.has(s.degree_id));
}
