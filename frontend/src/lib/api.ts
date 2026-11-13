// Cliente da API local (/api). Erros viram ApiError com a mensagem do backend.

class ApiError extends Error {
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
  counters: {
    contents: Counter;
    exercises: Counter;
    mocks: Counter;
    lab: Counter;
  };
  progress_as_of: string | null;
  exam: ExamInfo | null;
  exam_requires_lab: boolean;
  lab_pending: boolean;
  pending_topics: { id: number; title: string }[];
  grade: GradePrediction | null;
}

/** v1.5 (D30): nota prevista pela regra da disciplina */
export interface GradePrediction {
  label: string;
  to_check: boolean;
  pass_min: number;
  max_total: number;
  parts: {
    key: string;
    label: string;
    max: number;
    value: number | null;
    source: string | null;
    source_label: string;
    pending: number;
  }[];
  total: number | null;
  passed: boolean | null;
  known_total: number;
  needed: { key: string; label: string; value: number | null; possible: boolean } | null;
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
  done?: boolean;
  /** Tipo do item (Prova/AV, Prazo, Laboratório, Simulado...) */
  label?: string;
}

export interface Overview {
  today: string;
  semester: { id: number; code: string; degree_name: string } | null;
  subjects: SubjectOverview[];
  upcoming_exams: (ExamInfo & { subject_id: number; subject_name: string })[];
  next_action: NextActionAny | null;
  week: {
    start: string;
    days: { date: string; seconds: number }[];
    total_seconds: number;
    goal_hours: number | null;
  };
  timeline: { date: string; items: TimelineItem[] }[];
  timer: { goal_minutes: number; alarm_minutes: number };
  /** v1.6 (D35): cards vencidos hoje */
  cards_due: number;
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
  done_at?: string | null;
}

export type DeadlineKind = "deadline" | "event" | "lab" | "activity" | "mock";

export interface Deadline {
  id: number;
  subject_id: number | null;
  title: string;
  due_date: string;
  kind: DeadlineKind;
  gcal_event_id: string | null;
  notes: string | null;
  done_at?: string | null;
  total_questions?: number | null;
  first_try_correct?: number | null;
  wrong_attempts?: number | null;
  score?: number | null;
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
  answer: {
    chosen_index: number;
    is_correct: boolean;
    correct_index: number;
    explanation: string | null;
  } | null;
}

export interface QuestionSetView {
  id: number;
  topic_id: number | null;
  topic_title: string;
  subject_id: number | null;
  attempt_type: string;
  label?: string;
  time_limit_minutes?: number | null;
  seconds_left?: number | null;
  created_at?: string | null;
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
  status: MistakeStatus;
  status_label: string;
  subject_id: number;
}

/** v1.5 (D28): ciclo dos erros */
export type MistakeStatus = "open" | "reviewed" | "again" | "fixed";
export type MistakeCounts = Record<MistakeStatus, number>;

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
  categories: {
    category: string;
    registered: number;
    counted: number;
    planned: number;
    cap: number | null;
  }[];
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
    subjects: {
      id: number;
      name: string;
      hours: number | null;
      status: string;
    }[];
  }[];
  unscheduled: {
    id: number;
    name: string;
    hours: number | null;
    status: string;
  }[];
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

// --- v1.3: lado Estudo (provas e prazos, histórico, semana, prints) ------------------

export interface AgendaItem {
  type: "exam" | "deadline";
  id: number;
  subject_id: number | null;
  subject_name: string | null;
  title: string;
  kind: string;
  kind_label: string;
  date: string | null;
  time: string | null;
  to_schedule: boolean;
  location: string | null;
  score: number | null;
  total_questions?: number | null;
  first_try_correct?: number | null;
  wrong_attempts?: number | null;
  done: boolean;
  notes: string | null;
  notion_page_id?: string | null;
  /** v1.5: nota máxima (simulado vale 1,0; prova segue a regra da disciplina) */
  max_score: number;
}

export interface HistorySet {
  id: number;
  topic_id: number | null;
  topic_title: string;
  subject_id: number | null;
  subject_name: string | null;
  attempt_type: string;
  label: string;
  score: number | null;
  questions: number;
  answered: number;
  right: number;
  wrong: number;
  created_at: string | null;
  completed_at: string | null;
  time_limit_minutes: number | null;
  model: string;
}

export interface TopicEvolution {
  topic_id: number;
  topic_title: string;
  subject_id: number;
  subject_name: string;
  status: "pending" | "learned" | "review";
  open_mistakes: number;
  mistakes: MistakeCounts;
  cards: number;
  has_text: boolean;
  points: {
    set_id: number;
    date: string;
    score: number | null;
    label: string;
  }[];
}

export interface WeekSummary {
  start: string;
  seconds: number;
  sets: number;
  average_score: number | null;
  topics_learned: number;
  items_done: number;
}

export interface PrintReadingView {
  label: string;
  question_number: number | null;
  result: "correct" | "wrong" | "unknown";
  note: string;
}

export interface PrintProposal {
  images: number;
  readings: PrintReadingView[];
  total_questions: number;
  first_try_correct: number;
  wrong_attempts: number;
  score: number | null;
  unknown: number;
}

export interface FolderListing {
  path: string;
  entries: {
    name: string;
    path: string;
    type: "dir" | "image" | "pdf" | "transcript";
    size?: number;
  }[];
}

// --- v1.4: cronômetro e desempenho ------------------------------------------------

export interface TimerSessionView {
  id: number;
  subject_id: number | null;
  subject_name: string | null;
  started_at: string;
  ended_at: string | null;
  pauses: number;
  active_seconds: number;
  wall_seconds: number | null;
  end_reason: "finished" | "reset" | null;
  notes: string | null;
}

export interface Metrics {
  start: string;
  end: string;
  days: number;
  totals: {
    seconds: number;
    sets: number;
    questions: number;
    accuracy: number | null;
    average_score: number | null;
    study_days: number;
    streak: number;
    cards_reviewed: number;
  };
  daily: { date: string; seconds: number; sets: number; cards: number; average_score: number | null }[];
  subject_id: number | null;
  scores: {
    set_id: number;
    date: string;
    score: number | null;
    label: string;
    attempt_type: string;
    topic: string | null;
    subject: string | null;
  }[];
  by_subject: {
    subject_id: number;
    name: string;
    seconds: number;
    sets: number;
    average_score: number | null;
    topics_total: number;
    topics_learned: number;
    topics_review: number;
    open_mistakes: number;
    mistakes: MistakeCounts;
  }[];
  topics: { pending: number; review: number; learned: number };
  timer: {
    sessions: number;
    active_seconds: number;
    wall_seconds: number;
    average_active: number | null;
    average_pauses: number | null;
    focus: number | null;
  };
  graded: {
    title: string;
    kind: string;
    score: number;
    max_score: number;
    wrong_attempts: number | null;
    date: string | null;
  }[];
}

/** v1.5: o que foi feito num dia (clique na barra do gráfico) */
export interface DayDetail {
  date: string;
  seconds: number;
  chunks: { started_at: string; ended_at: string | null; seconds: number; subject_name: string | null }[];
  sets: HistorySet[];
  tasks: { id: number; label: string; done: boolean; planned_minutes: number | null }[];
}

export interface ChatMessageView {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string | null;
}

export interface ExamSyncPreview {
  id: number;
  title: string;
  scheduled_at: string;
  sent: boolean;
}

// --- Cards de estudo (v1.6, D32–D37) ---------------------------------------------

export interface CardView {
  id: number;
  topic_id: number;
  topic_title: string;
  subject_id: number | null;
  subject_name: string;
  kind: "concept" | "question" | "confusion";
  kind_label: string;
  mode: "answer" | "flip";
  front: string;
  back: string;
  explanation: string | null;
  options: string[] | null;
  correct_index: number | null;
  source: "mistake" | "text" | "print" | "video";
  source_label: string;
  source_detail: string | null;
  mistake_id: number | null;
  mistake_status: MistakeStatus | null;
  chosen_text: string | null;
  video_minute: string | null;
  notion_url: string | null;
  step: number;
  next_review: string;
  due: boolean;
}

export interface CardReviewResult {
  knew: boolean;
  correct_index: number | null;
  card: CardView;
}

export interface CardsSummary {
  due: number;
  total: number;
  topics: {
    topic_id: number;
    topic_title: string;
    subject_id: number;
    subject_name: string;
    total: number;
    due: number;
    reviews: number;
    knew: number;
    has_notion: boolean;
  }[];
}

// --- v1.8: cursos e certificados (SPEC §18) ---------------------------------------

export type Area = "faculdade" | "cursos";
export type CourseType = "course_certificate" | "certification" | "language" | "bootcamp" | "free";
export type CourseStatus = "wishlist" | "doing" | "paused" | "done";

export interface CourseLesson {
  id: number;
  title: string;
  done: boolean;
  has_text: boolean;
  last_score: number | null;
  notion_page_id: string | null;
  learning_status: string;
}

export interface CourseModule {
  id: number;
  name: string;
  status: string;
  number: number;
  lessons: CourseLesson[];
}

export interface Course {
  id: number;
  name: string;
  platform: string | null;
  course_type: CourseType;
  type_label: string;
  url: string | null;
  course_status: CourseStatus;
  status_label: string;
  total_hours: number | null;
  start_date: string | null;
  target_date: string | null;
  days_to_target: number | null;
  certificate_path: string | null;
  counts_acc: boolean;
  acc_category: string | null;
  notion_page_id: string | null;
  notion_url: string | null;
  exam_at: string | null;
  days_to_exam: number | null;
  manual_progress: number | null;
  notes: string | null;
  finished_on: string | null;
  acc_activity_id: number | null;
  modules_total: number;
  modules_done: number;
  progress: number;
  seconds: number;
  week_seconds: number;
  sets: number;
  average_score: number | null;
  cards: number;
  next_lesson: {
    module_id: number;
    module: string;
    module_number: number;
    topic_id: number | null;
    title: string | null;
  } | null;
  modules?: CourseModule[];
}

export interface CoursesSummary {
  week_seconds: number;
  goal_hours: number | null;
  certificates: number;
  acc_hours: number;
  counts: Record<CourseStatus, number>;
  next_exam: { course_id: number; name: string; exam_at: string; days: number } | null;
}

export interface CourseModuleOption {
  id: number;
  name: string;
  course_id: number;
  course_name: string;
}
