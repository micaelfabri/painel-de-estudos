import { useLocation } from "react-router-dom";

import type { Area, CourseModuleOption, Degree, Overview, Semester, Subject } from "@/lib/api";
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

export type CollegeSubject = Subject & { label: string };

/**
 * Disciplinas só da faculdade (D38/D42): os módulos dos cursos não entram em provas e prazos.
 * v1.8.2: o rótulo leva o semestre ("Banco de Dados · 2025.2"), porque uma disciplina repetida aparece duas
 * vezes com o mesmo nome; o semestre atual vem primeiro, depois os outros do mais novo para o mais antigo.
 */
export function useCollegeSubjects(): CollegeSubject[] {
  const degrees = useApi<Degree[]>("/degrees");
  const subjects = useApi<Subject[]>("/subjects");
  const semesters = useApi<Semester[]>("/semesters");
  const ids = new Set((degrees.data ?? []).filter((d) => d.kind === "degree").map((d) => d.id));
  const sem = new Map((semesters.data ?? []).map((x) => [x.id, x]));
  const rank = (s: Subject) => {
    const x = s.semester_id !== null ? sem.get(s.semester_id) : undefined;
    return x ? [x.is_current ? 0 : 1, x.code] : [2, ""];
  };
  return (subjects.data ?? [])
    .filter((s) => ids.has(s.degree_id))
    .map((s) => {
      const x = s.semester_id !== null ? sem.get(s.semester_id) : undefined;
      return { ...s, label: `${s.name} · ${x ? `${x.code}${x.is_current ? " (atual)" : ""}` : "sem semestre"}` };
    })
    .sort((a, b) => {
      const [ga, ca] = rank(a);
      const [gb, cb] = rank(b);
      if (ga !== gb) return (ga as number) - (gb as number);
      if (ca !== cb) return (cb as string).localeCompare(ca as string); // semestre mais novo primeiro
      return a.name.localeCompare(b.name, "pt-BR");
    });
}
