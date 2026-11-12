// Cliente da API local (/api). Erros viram ApiError com a mensagem do backend.

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      /* resposta sem JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body: unknown, signal?: AbortSignal) => request<T>("POST", path, body, signal),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: (path: string) => request<void>("DELETE", path),
};

// --- Tipos da visão do painel -------------------------------------------------

export type Counter = [number, number] | null;

export interface ExamInfo {
  id: number;
  kind: string;
  scheduled_at: string | null;
  schedule_by: string | null;
  location: string | null;
  date: string;
  days_left: number;
}

export interface SubjectOverview {
  id: number;
  name: string;
  hours: number | null;
  percent: number | null;
  counters: { contents: Counter; exercises: Counter; mocks: Counter; lab: Counter };
  progress_as_of: string | null;
  exam: ExamInfo | null;
  exam_requires_lab: boolean;
  lab_pending: boolean;
  pending_topics: { id: number; title: string }[];
}

export type NextActionAny = NextAction | ReviewAction;

export interface ReviewAction {
  kind: "review";
  review_id: number;
  subject_id: number;
  subject_name: string;
  topic_id: number;
  steps: string[];
  due_date: string;
  reviews_due: number;
  after: { subject_id: number; subject_name: string; exam_date: string } | null;
}

export interface NextAction {
  kind: "study";
  subject_id: number;
  subject_name: string;
  topic_id: number | null;
  steps: string[];
  exam_date: string;
  exam_days_left: number;
  exam_scheduled: boolean;
  percent: number | null;
  after: { subject_id: number; subject_name: string; exam_date: string } | null;
}

export interface TimelineItem {
  category: "exam" | "deadline" | "event";
  title: string;
  time: string | null;
}

export interface Overview {
  today: string;
  semester: { id: number; code: string; degree_name: string } | null;
  subjects: SubjectOverview[];
  upcoming_exams: (ExamInfo & { subject_id: number; subject_name: string })[];
  next_action: NextActionAny | null;
  week: { start: string; days: { date: string; seconds: number }[]; total_seconds: number; goal_hours: number | null };
  timeline: { date: string; items: TimelineItem[] }[];
  timer: { goal_minutes: number; alarm_minutes: number };
}

// --- Tipos dos cadastros -------------------------------------------------------

export interface Degree {
  id: number;
  name: string;
  institution: string | null;
  kind: string;
  status: string;
  curriculum: string | null;
  total_hours: number | null;
  reported_done_hours: number | null;
  reported_at: string | null;
  expected_end: string | null;
  notes: string | null;
}

export interface Semester {
  id: number;
  degree_id: number;
  code: string;
  start_date: string | null;
  end_date: string | null;
  is_current: boolean;
  notes: string | null;
}

export interface Subject {
  id: number;
  degree_id: number;
  semester_id: number | null;
  component_id: number | null;
  name: string;
  code: string | null;
  hours: number | null;
  status: "pending" | "in_progress" | "passed" | "failed";
  grading_rule: Record<string, unknown> | null;
  exam_requires_lab: boolean;
  notes: string | null;
}

export interface Topic {
  id: number;
  subject_id: number;
  position: number;
  title: string;
  portal_done: boolean;
  learning_status: "pending" | "learned" | "review";
  notion_page_id: string | null;
  source_text: string | null;
  notes: string | null;
}

export interface Exam {
  id: number;
  subject_id: number;
  kind: string;
  scheduled_at: string | null;
  schedule_by: string | null;
  location: string | null;
  score: number | null;
  gcal_event_id: string | null;
  notes: string | null;
}

export interface Deadline {
  id: number;
  subject_id: number | null;
  title: string;
  due_date: string;
  kind: "deadline" | "event";
  gcal_event_id: string | null;
  notes: string | null;
}

export interface PortalProgress {
  percent: number | null;
  contents_done: number | null;
  contents_total: number | null;
  exercises_done: number | null;
  exercises_total: number | null;
  mocks_done: number | null;
  mocks_total: number | null;
  lab_done: number | null;
  lab_total: number | null;
  as_of: string | null;
}

export interface SettingsResponse {
  values: Record<string, unknown>;
  schema: { key: string; default: unknown; description: string }[];
}

// --- Agente ---------------------------------------------------------------------

export interface ModelsInfo {
  base_url: string;
  reachable: boolean;
  models: string[];
  default_model: string | null;
  error: string | null;
}

export interface QuestionView {
  id: number;
  position: number;
  statement: string;
  options: string[];
  flagged_bad: boolean;
  answer: { chosen_index: number; is_correct: boolean; correct_index: number; explanation: string | null } | null;
}

export interface QuestionSetView {
  id: number;
  topic_id: number;
  topic_title: string;
  subject_id: number;
  attempt_type: string;
  model: string;
  prompt_version: string;
  summary: string | null;
  score: number | null;
  completed_at: string | null;
  questions: QuestionView[];
}

export interface AnswerResult {
  is_correct: boolean;
  correct_index: number;
  explanation: string | null;
  mistake_id: number | null;
  set_score: number | null;
  set_completed: boolean;
}

export interface Mistake {
  id: number;
  question_id: number;
  topic_id: number;
  video_minute: string | null;
  reviewed: boolean;
  notes: string | null;
}

/** Mensagem de erro do backend do agente: {message, status} ou texto */
// Mensagens de erro na conversa ficam curtas: nunca despejar o texto do tema nem um log inteiro
const MAX_ERROR_CHARS = 300;

export function agentErrorMessage(err: unknown): string {
  const message = rawAgentErrorMessage(err);
  return message.length > MAX_ERROR_CHARS ? `${message.slice(0, MAX_ERROR_CHARS).trimEnd()}…` : message;
}

function rawAgentErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    try {
      const parsed = JSON.parse(err.message);
      if (parsed && typeof parsed.message === "string") return parsed.message;
      // Erro de validação do FastAPI (lista): mostra a mensagem, nunca o texto enviado
      if (Array.isArray(parsed) && parsed[0]?.type === "string_too_long")
        return `Texto longo demais: o limite é ${parsed[0].ctx?.max_length ?? "30000"} caracteres. Cole uma parte por vez.`;
      if (Array.isArray(parsed) && typeof parsed[0]?.msg === "string") return `Dados inválidos: ${parsed[0].msg}`;
    } catch {
      /* não era JSON */
    }
    return err.message;
  }
  return err instanceof Error ? err.message : "Erro desconhecido";
}

// --- Aprendizado (F4) -------------------------------------------------------------

export interface ReviewDue {
  id: number;
  topic_id: number;
  topic_title: string;
  subject_id: number;
  subject_name: string;
  attempt_type: string;
  label: string;
  due_date: string;
  has_text: boolean;
}

export interface TopicScore {
  topic_id: number;
  topic_title: string;
  subject_id: number;
  subject_name: string;
  status: "pending" | "learned" | "review";
  first_score: number | null;
  decisive_score: number | null;
  last_score: number | null;
  last_attempt: string;
  attempts: number;
  next_review: { date: string; label: string } | null;
}

export interface ChecklistItem {
  id: number;
  day: string;
  label: string;
  planned_minutes: number | null;
  topic_id: number | null;
  review_id: number | null;
  done: boolean;
  position: number;
}

export interface MistakeReview {
  id: number;
  topic_id: number;
  topic_title: string;
  subject_name: string;
  statement: string;
  options: string[];
  correct_index: number;
  chosen_index: number | null;
  explanation: string | null;
  video_minute: string | null;
  reviewed: boolean;
}

// --- Curso e ACC (F6) ---------------------------------------------------------------

export interface CourseComponent {
  id: number;
  name: string;
  kind: "subjects" | "acc" | "manual";
  required_hours: number | null;
  baseline_hours: number;
  from_panel_hours: number;
  done_hours: number;
  percent: number | null;
  to_check: boolean;
  notes: string | null;
}

export interface AccSummary {
  required_hours: number | null;
  counted_hours: number;
  planned_hours: number;
  missing_hours: number | null;
  rules_known: boolean;
  categories: { category: string; registered: number; counted: number; planned: number; cap: number | null }[];
}

export interface CourseProgress {
  degree: {
    id: number;
    name: string;
    institution: string | null;
    curriculum: string | null;
    total_hours: number | null;
    reported_done_hours: number | null;
    reported_at: string | null;
    expected_end: string | null;
  };
  done_hours: number;
  percent: number | null;
  components: CourseComponent[];
  acc: AccSummary | null;
  semesters: {
    id: number;
    code: string;
    is_current: boolean;
    subjects: { id: number; name: string; hours: number | null; status: string }[];
  }[];
  unscheduled: { id: number; name: string; hours: number | null; status: string }[];
}

export interface AccActivity {
  id: number;
  degree_id: number;
  title: string;
  category: string | null;
  hours: number;
  activity_date: string | null;
  certificate_path: string | null;
  status: "registered" | "planned";
  notes: string | null;
}

// --- Integrações (F5) ------------------------------------------------------------

export interface NotionPage {
  id: string;
  title: string;
  url: string | null;
  last_edited: string | null;
}

export interface NotionStatus {
  configured: boolean;
  reachable: boolean;
  pages: number;
  pending_results: number;
  error: string | null;
}

export interface GoogleStatus {
  client_file: boolean;
  connected: boolean;
  calendar_id: string | null;
  calendar_name: string;
}

export interface GoogleEvent {
  title: string;
  date: string;
  time: string | null;
}
