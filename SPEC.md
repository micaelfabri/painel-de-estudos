# SPEC — Painel de Estudos (painel-de-estudos)

Version 1.8 · 13/11/2026 · Owner: (seu nome aqui) · Builder: Claude Code
Bilingual file (DIRETRIZ_BILINGUE_v1): English first, Portuguese after. If they differ, the Portuguese prevails.

---

## ENGLISH

### 1. Problem
Studying one topic of my EAD degree takes 3 to 6 hours (portal, videos, screenshots, copying to Notion). My schedule allows 1 topic per day. I don't know how much I'm learning, I lose rhythm after weeks without studying, and I have no single view of exams, deadlines and progress. It must run on the PC (phone apps distract me).

### 2. Goal
One local page that shows where I stand in every subject and a local study agent that turns each topic into a short summary + exam-style questions, scores my answers and schedules retests. Success = I know, per topic, whether I learned it (score on the 7-day retest), not only how many hours I spent.

### 3. Non-goals (do not build)
- Hosting (Vercel, VPS), public URL, login/admin.
- Cloud LLMs inside the agent (Claude, Gemini). Claude is the builder only.
- Automatic sync with the PDI site (copying numbers is manual).
- RAG over course files, fine-tuning, mobile app.
- Scraping the faculty portal (no API; progress is typed).
- Deleting Google Calendar events — ever.

### 4. Decisions (09/11/2026)
| # | Decision |
|---|---|
| D1 | Runs only on my PC at `localhost`, while the PC is on. Docker Compose, one app container, port bound to `127.0.0.1`. |
| D2 | No login. Two modes in the UI: **Study** (panel + agent) and **Manage** (edit data). The mode switch is navigation: two route links with the TabsList look in the topbar; below `sm`, they move into the sidebar menu. |
| D3 | Model runs on Windows (Ollama, or LM Studio as an alternative). The app calls it over the OpenAI-compatible API. Model selector in the UI + saved default. |
| D4 | Backend: Python + FastAPI + SQLite (one file in `./data`). |
| D5 | Frontend: React + Vite + Tailwind v4, own design system (design pattern), **Application surface**, DS v2.13 (sidebar + topbar, 14px base, border cards, dark mode). The panel's own `tema.css` changes only the primary family (purple). Light: `--primary` #7c3aed · `--primary-hover` #6d28d9 · `--primary-text` #7c3aed · `--ring` #7c3aed · `--accent` #f5f3ff · `--accent-foreground` #5b21b6. Dark: `--primary` #7c3aed · `--primary-hover` #6d28d9 · `--primary-text` #a78bfa · `--ring` #a78bfa · `--accent` #2e1065 · `--accent-foreground` #c4b5fd. Charts: `--chart-1` purple (#7c3aed / #a78bfa), `--chart-4` blue (#2563eb / #60a5fa). Everything else is the DS default. |
| D6 | Notion: official API, internal integration, read + write only on the study pages shared with it. Each topic links to its page; the result of each question set is appended as a block at the end of the page (date, type, score, wrong questions); never deletes (decided 10/11/2026). |
| D7 | Google Calendar: official API, read + write. The app creates/edits exam and event entries; it only edits events it created (private extended property `painel=1`); it never deletes. Decided 10/11/2026: the app writes only to its own "Painel de Estudos" calendar (scope `calendar.app.created`) and reads the main calendar (scope `calendar.events.readonly`); the Google app stays in Testing mode (sign-in again about every 7 days) until there are public home and privacy pages. |
| D8 | Portal progress: typed in Manage mode. |
| D9 | Learning: first score + retests at 1, 7 and 21 days; "learned" = 70%+ on the 7-day retest. |
| D10 | ACC (complementary activities): module to register hours and track them against the required total. |
| D11 | Private repo; later a public copy with mock data for the portfolio. |
| D12 | AI engineering items (aligned with iFood GenAI, AI Engineer track): model eval, structured outputs, versioned prompts, usage log. |

### 5. Data hierarchy
Degree → Semester → Subject → Topic. Covers the current degree (e.g. Engenharia de Software, 2024–2028), a finished earlier degree (review only) and parallel courses/certificates (online courses, languages…). Each level has its own deadlines, grading rule and progress.

Grading rule is data, not code. Example rules, taken from real 2026 teaching plans (pass with 6+):
- Standard: AV/AVS 0–8 + Progresso Acadêmico 0–2.
- Padrões de Projeto: AV/AVS 0–10, in person, 75% attendance.
- Arquitetura de Sistemas: AV/AVS 0–10 + AP 0–2; AP only counts if AV/AVS ≥ 4.
- Extensionistas: own rule (extension activity 2 points + mock tests).
- Subjects with a lab: the exam unlocks only after the lab.

Note: the e-book "Por dentro das avaliações" (jan/2024) describes AV 0–10 with optional AVAs worth up to +2; the 2026 teaching plans describe AV/AVS 0–8 + Progresso Acadêmico 0–2. The panel follows the 2026 teaching plans until confirmed.

### 6. Modules

**6.1 Panel (Study mode)** — reference: mockup of 09/11 (layout only).
- Next exam: countdown in days + the following exams.
- Study timer: goal 1h30 per topic, alarm at 2h, pause/finish; each session is saved.
- Hours this week vs weekly goal, bars per day.
- One card per subject: portal % , exam badge (date/time or "schedule by"), counters x/y (contents, exercises, mock tests, lab).
- Next suggested action (rule-based: nearest exam × lowest progress × pending retests).
- 14-day timeline (exams, deadlines, calendar events).
- % correct per topic (first score and retests), as an inline meter with the 70% threshold; at 70%+ it shows success + icon + "Aprendido".
- Calendar study blocks (read from Google Calendar).

**6.2 Agent (right panel)**
- From `lg`: third column of the layout. Below `lg`: side sheet opened by a topbar button ("Abrir agente"); its state is kept when it closes.
- Today's checklist: topics planned + retests due. Checking a task marks it done immediately (DS exception E11).
- Chat box: "paste the topic text or ask something". While the local model answers: "Pensando…", seconds shown after 5 s, Cancel after 10 s; errors appear in the list with "Tentar de novo".
- Buttons: Generate questions, Review mistakes, Timer.
- Exam style: 10 multiple-choice questions per set (e-book jan/2024). Number of options per question is a setting, still unknown (to confirm from a real exam or mock test).
- Core loop: topic text (pasted or read from Notion) → short summary + 10 exam-style questions → I answer without looking → app scores → wrong answers go to the mistakes log, each with an optional "video minute" field I fill in → results written back to Notion and to the panel.
- I can flag a bad question; flagged questions don't count in the score.

**6.3 Learning measurement**
- Attempt types: `first`, `retest_1d`, `retest_7d`, `retest_21d`. Retests use new questions on the same topic.
- Topic status: `pending` (no 7-day retest yet), `learned` (7-day retest ≥ 70%), `review` (7-day retest < 70% → new retest in 3 days).
- Hours are shown as context only.

**6.4 Manage mode**
- CRUD: degrees, semesters, subjects (with grading rule), topics, exams, deadlines.
- Portal progress entry per subject.
- Settings: default model, weekly hours goal, timer goal/alarm, Notion page IDs, calendar ID.
- Usage log view (see 7).

**6.5 ACC**
- Entry: activity, category, hours, date, certificate path (local file), notes.
- Required total: 100h. Starting point: the hours already computed in the academic record, entered as one opening entry.
- Progress bar against the 100h. Categories, per-category or per-activity limits, deadline and proof: unknown — optional fields, filled in when the AAC regulation arrives (see 11).

**6.6 Course progress**
- Total hours, hours done per component and the baseline date come from the academic record.
- Components with done/required hours: mínima 1,040/2,860h; extensionistas 144/240h; AAC 16/100h (fictional demo values); optativa 0/560h; estágio 0h (required total not registered).
- The optativa doesn't fit the 3,200h sum: shown with a "to check" flag until confirmed.
- Hours of each subject count toward its component when the subject is marked as passed.

### 7. AI engineering (the agent's quality controls)
- **Model eval (phase 0):** `eval/` folder. 3 real topics × 2–3 local models. Measures: valid JSON rate, time per answer, my 1–5 rating of summary and questions in Portuguese. Output: `eval/RESULTS.md` with the chosen default model and why.
- **Structured outputs:** every LLM call returns JSON validated against a Pydantic schema (summary, questions, options, answer key, explanation). Invalid JSON → one retry → error shown, nothing saved.
- **Versioned prompts:** prompts live in `backend/prompts/*.md` under git; each question set stores the prompt version and model used.
- **Usage log:** table `llm_call` (model, prompt version, input/output tokens, latency, ok/error), visible in Manage mode.

### 8. Architecture
```
Browser (localhost:8000)
   │
Docker: app container (FastAPI serves API + built React)
   ├── SQLite ./data/painel.db (volume)
   ├── Notion API (internet, token in .env)
   ├── Google Calendar API (internet, OAuth token in ./secrets)
   └── LLM: http://host.docker.internal:11434/v1 (Ollama) or :1234/v1 (LM Studio)
Windows host: Ollama / LM Studio using the local GPU
```
To verify in phase 0: the container reaching Ollama on the host without exposing Ollama to the local network.

### 9. Data model (initial)
`degree`, `degree_component` (name, required_hours, done_hours, to_check), `semester`, `subject` (grading_rule JSON, hours, component, exam_requires_lab), `topic`, `exam`, `deadline`, `portal_progress`, `study_session`, `question_set` (topic, model, prompt_version, attempt_type), `question`, `answer`, `mistake` (question, video_minute), `review_schedule`, `acc_activity`, `acc_rule`, `llm_call`, `setting`.

### 10. Security and privacy
- App port bound to `127.0.0.1` only.
- `.env` and `./secrets/` in `.gitignore`; no tokens in code or logs.
- Notion integration sees only the pages I share with it.
- Calendar: never delete; only edit events with `painel=1`.
- Public portfolio copy: mock data only, no grades, no real Notion or Calendar data.
- Prints of my answers go only to the local model (D17), and only from linked Notion pages or the materials folder (D18).

### 11. Pending
Requests to the faculty chat (prints from the portal):
- AAC regulation or the portal's AAC screen (categories, limits, deadline, proof).
- Full curriculum matrix, curriculum 202202 (split of the pending subjects by semester, hours).
- Number of options per question (print of a past AV or mock test).
- Which grading rule applies today: e-book jan/2024 vs 2026 teaching plans.
- 2027.1 calendar (start, exams, scheduling deadlines). Known so far: pre-enrollment 22/10–25/11/2026.

### 12. Phases
| Phase | Content | Done when |
|---|---|---|
| F0 | Repo, Docker, model eval | `eval/RESULTS.md` names the default model |
| F1 | Backend base, data model, Manage mode CRUD, portal progress, seed (see 13) | I can register the current semester and see it saved |
| F2 | Frontend shell with DS + Panel (cards, next exam, timer, hours, timeline, next action) | Panel shows the current semester with the seed data |
| F3 | Agent: summary + questions, answering, scoring, mistakes, model selector, usage log | One full topic cycle works end to end |
| F4 | Retests 1/7/21, topic status, % per topic, Review mistakes | A retest appears on the right day and changes the status |
| F5 | Notion (read topic text, write results) + Google Calendar (read, create/edit own events) | Topic read from Notion; exam created in Calendar |
| F6 | ACC module | ACC hours tracked against the total |
| F7 | Public copy with mock data + README | Public repo runs with mock data |

Build starts after 08/12/2026.

### 13. Initial seed (F1)

This public copy ships with **fictional data** (`backend/app/seed.py`): an example degree, five current subjects with exams, portal progress, pending subjects and an ACC starting entry. The real data lives only in the owner's private copy.

### 14. Version 1.3 (12/11/2026, after the first real use)
| # | Decision |
|---|---|
| D13 | Study mode gets three pages: **Painel**, **Provas e prazos** and **Histórico**. |
| D14 | **Provas e prazos** (study side): exams, deadlines, events, labs and activities in one list; each one can be edited and marked done. Labs and activities are deadlines of kind `lab` / `activity`. |
| D15 | **Histórico**: every question set stays saved and visible (date, type, topic, score), per-topic evolution, and three actions: redo the wrong questions (no model call), new test based on my mistakes, new test based on my right answers. |
| D16 | **Exam simulation**: one set that mixes the topics of one subject, same size as the real exam (settings: 10 questions, 60 minutes), with a countdown. Counts in history, not in the topic retest cycle. |
| D17 | **Scores from prints**: the agent reads the images of a Notion page linked to a topic, or files in the course materials folder (read-only), with a **local vision model**. Rule: a print with only the right answer = right first time; each print with a wrong answer = one wrong attempt. Score = right first time ÷ total questions × 10, shown together with the total wrong attempts. The agent only **proposes**; nothing is saved until I confirm. |
| D18 | **Materials folder**: only the course materials folder set in `.env` (`PAINEL_MATERIALS_HOST`), mounted read-only in the container. Nothing else on the PC is read. Images and PDFs now; videos later. |
| D19 | Editing on the study side: rename checklist tasks, edit topics, mark deadlines/events/labs done. |
| D20 | Weekly summary card (hours, sets, average score, topics learned this week) and automatic daily backup of `painel.db` in `./data/backups` (keeps the last 14). |
| D21 | Footer: "© <year> Painel de Estudos", links to GitHub and LinkedIn (set in Settings) and "Site (em breve)" without a link. |
| D22 | **Later version (V3–V5, not now):** asking and giving commands to the agent by voice, with a maximum recording length; local speech-to-text, no cloud. Supported models and requirements are checked before building. The agent answering in voice comes much later. |

| Phase | Content | Done when |
|---|---|---|
| F8 | D13–D21 | A retest stays in Histórico after F5 (page reload); a lab is marked done; a print-based score is proposed and confirmed |

### 15. Version 1.4 (12/11/2026)
| # | Decision |
|---|---|
| D23 | **14-day strip** as approved: two rows of 7 days, counts per type in each day (exam, deadline/lab/activity/mock, calendar event), click a day to see its list with times; done items struck through. |
| D24 | **Timer sessions**: from the first Iniciar to Finalizar is one session. It counts pauses, sums the studied chunks and keeps a hidden clock from start to end (pauses included). "Finalizar" closes the session; every finished session is saved and listed on the Painel and in Desempenho. v1.7.2 (13/11/2026): "Zerar" became "Cancelar", which discards the session and its chunks after a confirmation (old "zerada" sessions stay). |
| D25 | **Desempenho** page (Study mode): hours per day, test scores over time with the 70% line, accuracy, streak, per-subject numbers (hours, tests, average, topics learned, open mistakes), timer focus (studied ÷ total) and pauses, scores of exams/labs/mocks. Period 7/30/90 days. The agent reads a short summary of these numbers (local model only); authorized by me on 12/11/2026, on by default and can be turned off in Settings. |
| D26 | **Mocks** ("simulados" of the college): own deadline kind `mock`; each current subject has 2 (10 questions, up to 1.0 point each). Labs, activities and mocks can link their **own Notion page**, used to read the prints. |
| D27 | Footer links in the official brand colors. |

| Phase | Content | Done when |
|---|---|---|
| F9 | D23–D27 | A timer session with 2 pauses is finished and listed with studied time, total time and pauses; the lab's own Notion page is read |

### 16. Version 1.5 (12/11/2026)
| # | Decision |
|---|---|
| D28 | **Mistake cycle**: every mistake has a status: not reviewed → reviewed ("Já revisei") → in a redo, right = fixed, wrong = review again. A redo copy points to the original question and updates the original mistake; it never creates a new one. "Refazer erros não corrigidos" builds a set (up to 10, no model) from the mistakes not yet fixed, by topic, subject or all. Histórico, Desempenho and the agent summary show mistakes per status. Existing data was converted (redo copies merged into the original mistake). |
| D29 | **Topic status, rule "a"** (decided by me on 12/11/2026): the 7-day retest decides "learned"; a 21-day retest below 70% sends the topic back to "review" (+ 3-day retest). Redo, focus tests and mock exams don't change the status. |
| D30 | **Predicted grade** per subject on the Painel, from the grading rule (data): exam part = best exam score, Progresso Acadêmico = sum of the mocks (a mock without score counts 0 for now); shows the total or how much is needed in the AV/AVS to pass. Mock result is in points (right ÷ questions × 1.0); the exam score is capped by the rule (e.g. AV/AVS 0–8). The lab done flag in Provas e prazos decides "lab pending". |
| D31 | **Interactive charts** in Desempenho (hover/focus reads the value, click a day bar for that day's timer stretches and tests, click a score to open the test, subject filter); **confirmation** before marking an item done in Provas e prazos; "Mandar provas para a agenda" lists the exams and sends only the ticked ones; **agent chat saved** (survives reload, "Limpar conversa" with confirmation); the timer links a pause in the first second to its session. |

| Phase | Content | Done when |
|---|---|---|
| F10 | D28–D31 | A redo with 2 wrong answers leaves 2 "review again" and the rest "fixed" with no new mistakes; a chat message is still there after F5; clicking a score in Desempenho opens that test |

### 17. Version 1.6 (12/11/2026): cards from my weak points
Approved by me on 12/11/2026, with all of Claude's recommendations.

| # | Decision |
|---|---|
| D32 | **Cards from my weak points.** Chosen by weight: mistakes "review again" > "not reviewed" > topics in "Revisar" or below 70% in the last test > mistakes "reviewed"; ties go to the subject with the nearest exam. Card types: **concept** (front "what is X?", back 1–2 lines), **question turned card** (from a mistake: the question without options, back = right answer and why, plus what I picked), **mix-up** ("X vs Y", for mistakes where I picked a close option). Every card shows where to review: topic, Notion page, video minute when there is one. No two cards from the same mistake. |
| D33 | **Two ways to answer.** **Virar** (flip): I recall, flip, mark "Sabia" or "Não sabia". **Responder** (answer): 4 alternatives; the wrong ones come from mistakes I really made when they exist. Effect on the mistake cycle (D28) for cards that came from a mistake: "Não sabia" or wrong answer → "review again"; "Sabia" → "reviewed" (if it was "not reviewed"); right answer in Responder → "fixed". A card I keep getting right moves from Responder to Virar (recall is harder). |
| D34 | **Generation.** "Gerar cards" by topic, by subject or "my weak points"; 10 cards per generation by default. Sources in C1: my mistakes with their explanations, the topic text (`topic.source_text`) and the topic summary (now saved). New versioned prompt `generate_cards.v1`, through the single LLM client (Pydantic, 1 retry, `llm_call` log). Local model only. |
| D35 | **Repetition.** Each card has its own schedule, reusing the panel's intervals: new card → 1 day; "Sabia"/right → next step (1 → 7 → 21 → 60 days); "Não sabia"/wrong → back to 1 day. Due cards show in "Montar o dia" and "Próxima ação". |
| D36 | **Prints and videos as sources.** Authorized by me on 12/11/2026: prints of my answers (labs, mocks, exams, activities, from linked Notion pages or the materials folder) may be read by the **local model only** to transcribe the question and the right answer and turn them into cards (new prompt `read_print_card.v1`). Videos only after the voice phases (V3–V5), local only. My scores never go to the model as card material. |
| D37 | **Where it shows.** New **Cards** page in Study mode (generate, one row per topic with total and due today) and a **Cards** button in the agent panel (review one at a time). **Quick round** (minigame): about 10 cards in a row from my weak points, optional time per card, streak counter, short result at the end; no points or ranking. **Card of the day**: one card on the Painel and in "Montar o dia", from the weakest point of the subject with the nearest exam. Histórico shows cards per topic; Desempenho can show cards reviewed per day. **Notion export optional** (append only, never delete). |

Data: new tables `card` (front, back, type, mode, topic, source: mistake/text/print/video, source id, options, correct index, step, next review, prompt version, created at) and `card_review` (card, date, mode, knew/right yes/no). New migration; the daily backup covers it.

| Phase | Content | Done when |
|---|---|---|
| C1 | D32, D33, D34; review in the agent panel and the Cards page | "Gerar cards dos meus pontos fracos" creates 10 cards from my mistakes and topic text; I answer one in Virar and one in Responder, and the mistake it came from changes status as D33 says |
| C2 | D36 prints | A lab with a wrong print generates a card with that question and its right answer |
| C3 | D35, quick round, card of the day, optional Notion export | A card marked "Não sabia" is due again the next day; a quick round of 10 ends with the result; the card of the day shows on the Painel |
| C4 | D36 videos (after the voice phases) | A card cites a video passage transcribed locally |

### 18. Version 1.8 (13/11/2026): courses and certificates
Approved by me on 13/11/2026, with all of Claude's recommendations (mockups shown in the chat). Courses outside the college (free courses, courses with a certificate, certification exams, languages, bootcamps) get their own area, without mixing with the college.

| # | Decision |
|---|---|
| D38 | **Separate area.** The Study sidebar gets two groups: **Faculdade** (Painel, Provas e prazos, Histórico, Cards, Desempenho, as today) and **Cursos e certificados** (Meus cursos, Histórico, Cards, Desempenho). College pages show only the college (degrees of kind `degree`); course pages show only courses. The Painel stays college-only. |
| D39 | **A course reuses the hierarchy.** Course = `degree` of kind `course`, with: platform, type (curso com certificado, certificação com prova, idioma, bootcamp, curso livre), link, status (quero fazer, fazendo, pausado, concluído), total hours, start date, target date, certificate path (materials folder), counts as AAC (+ category), optional Notion page, exam date (certifications). Modules = subjects without a semester; lessons = topics. Questions, cards, timer, history, charts and the mistake cycle work for courses as they do for the college. Progress = modules done / total; without modules, a manual %. |
| D40 | **Day plan.** Courses do not enter "Montar o dia" (retests and next step) by default; a switch in Configurações turns them on. Inside a course, the agent generates questions and cards as usual. |
| D41 | **Hours.** Course hours count separately, with their own weekly goal (default 5 h, in Configurações). The college weekly hours and goal do not include them. The timer lists college subjects and course modules in separate groups. |
| D42 | **Certification exams** live only in the course area (course page and Meus cursos), not in Provas e prazos or the 14-day strip. |
| D43 | **AAC bridge.** When a course that counts as AAC is concluded, "Lançar como AAC" creates the AAC activity already filled (title, category, hours, date, certificate) and links it to the course, once; no double typing, no double counting. |
| D44 | **Notion.** Optional link to a Notion page per course (open the page); lessons can link Notion pages as topics already do. Same rules as today (never delete). |

Data: new columns on `degree` (platform, course_type, url, course_status, start_date, target_date, certificate_path, counts_acc, acc_category, notion_page_id, exam_at, manual_progress, acc_activity_id) and settings `course_weekly_goal_hours` and `courses_in_day_plan`. New migration; the daily backup covers it.

| Phase | Content | Done when |
|---|---|---|
| K1 | D38, D39: sidebar groups, Meus cursos (tabs by status, summary, course cards), Novo curso | I create a course with 9 modules; it shows under "Fazendo" with 0% and does not appear on the college Painel |
| K2 | Course page: modules and lessons, questions, cards and timer per course, D41, D42, D44 | I time 20 min on a module; it counts in "Horas em cursos" and not in the college week; a question set on a lesson shows in Cursos › Histórico only |
| K3 | Cursos › Histórico, Cards, Desempenho; D40 switch; D43 AAC bridge | A concluded course that counts as AAC creates one AAC activity with its hours, and the button disappears |

---

---

## PORTUGUÊS

### 1. Problema
Estudar um tema da faculdade EAD leva de 3 a 6 horas (portal, vídeos, prints, copiar para o Notion). Minha agenda comporta 1 tema por dia. Não sei o quanto estou aprendendo, perco o ritmo depois de semanas sem estudar e não tenho uma visão única de provas, prazos e progresso. Tem que rodar no PC (app no celular me distrai).

### 2. Objetivo
Uma página local que mostra onde estou em cada disciplina e um agente de estudos local que transforma cada tema em resumo curto + questões no estilo da prova, corrige minhas respostas e agenda retestes. Sucesso = saber, por tema, se aprendi (nota no reteste de 7 dias), não só quantas horas estudei.

### 3. Fora do escopo (não construir)
- Hospedagem (Vercel, VPS), URL pública, login/admin.
- LLM em nuvem dentro do agente (Claude, Gemini). O Claude só constrói.
- Sincronização automática com o site do PDI (copiar números é manual).
- RAG sobre os arquivos das matérias, fine-tuning, app de celular.
- Raspagem do portal da faculdade (sem API; progresso é digitado).
- Apagar eventos do Google Agenda — nunca.

### 4. Decisões (09/11/2026)
| # | Decisão |
|---|---|
| D1 | Roda só no meu PC em `localhost`, com o PC ligado. Docker Compose, um container do app, porta presa a `127.0.0.1`. |
| D2 | Sem login. Dois modos na interface: **Estudo** (painel + agente) e **Gerenciar** (editar dados). O seletor de modo é navegação: dois links de rota com visual de TabsList na topbar; abaixo de `sm`, vão para o menu da sidebar. |
| D3 | O modelo roda no Windows (Ollama, ou LM Studio como alternativa). O app chama pela API compatível com OpenAI. Seletor de modelo na interface + padrão salvo. |
| D4 | Backend: Python + FastAPI + SQLite (um arquivo em `./data`). |
| D5 | Frontend: React + Vite + Tailwind v4, padrão de design próprio, **superfície Aplicação**, DS v2.13 (sidebar + topbar, base 14px, cards com borda, modo escuro). O `tema.css` próprio do painel troca só a família primary (roxo). Claro: `--primary` #7c3aed · `--primary-hover` #6d28d9 · `--primary-text` #7c3aed · `--ring` #7c3aed · `--accent` #f5f3ff · `--accent-foreground` #5b21b6. Escuro: `--primary` #7c3aed · `--primary-hover` #6d28d9 · `--primary-text` #a78bfa · `--ring` #a78bfa · `--accent` #2e1065 · `--accent-foreground` #c4b5fd. Gráficos: `--chart-1` roxo (#7c3aed / #a78bfa), `--chart-4` azul (#2563eb / #60a5fa). Todo o resto é o padrão do DS. |
| D6 | Notion: API oficial, integração interna, leitura + escrita só nas páginas de estudo compartilhadas com ela. Cada tema é ligado à sua página; o resultado de cada conjunto de questões entra como um bloco no fim da página (data, tipo, nota, questões erradas); nunca apaga (decidido em 10/11/2026). |
| D7 | Google Agenda: API oficial, leitura + escrita. O app cria/edita marcações de provas e eventos; só edita eventos que ele criou (propriedade estendida privada `painel=1`); nunca apaga. Decidido em 10/11/2026: o app só escreve na agenda própria "Painel de Estudos" (escopo `calendar.app.created`) e lê a agenda principal (escopo `calendar.events.readonly`); o app do Google fica em modo Teste (login de novo a cada ~7 dias) até existirem páginas públicas de início e de privacidade. |
| D8 | Progresso do portal: digitado no modo Gerenciar. |
| D9 | Aprendizado: primeira nota + retestes em 1, 7 e 21 dias; "aprendido" = 70%+ no reteste de 7 dias. |
| D10 | ACC (atividades complementares): módulo para registrar horas e acompanhar contra o total exigido. |
| D11 | Repo privado; depois uma cópia pública com dados mock para o portfólio. |
| D12 | Itens de engenharia de IA (alinhados ao iFood GenAI, trilha AI Engineer): avaliação de modelos, saídas estruturadas, prompts versionados, registro de uso. |

### 5. Hierarquia dos dados
Graduação → Semestre → Disciplina → Tema. Cobre a graduação atual (ex.: Engenharia de Software, 2024–2028), uma graduação anterior concluída (só revisão) e cursos/certificados paralelos (cursos online, idiomas…). Cada nível tem prazos, regra de avaliação e progresso próprios.

Regra de avaliação é dado, não código. Regras de exemplo, tiradas de planos de ensino reais de 2026 (aprovação com 6+):
- Padrão: AV/AVS 0–8 + Progresso Acadêmico 0–2.
- Padrões de Projeto: AV/AVS 0–10, presencial, 75% de frequência.
- Arquitetura de Sistemas: AV/AVS 0–10 + AP 0–2; a AP só soma se a AV/AVS for 4 ou mais.
- Extensionistas: regra própria (atividade de extensão de 2 pontos + simulados).
- Disciplinas com laboratório: a prova só é liberada depois do laboratório.

Observação: o e-book "Por dentro das avaliações" (jan/2024) descreve AV de 0 a 10 com AVAs opcionais de até +2; os planos de ensino de 2026 descrevem AV/AVS 0–8 + Progresso Acadêmico 0–2. O painel segue os planos de ensino de 2026 até a confirmação.

### 6. Módulos

**6.1 Painel (modo Estudo)** — referência: mockup de 09/11 (só layout).
- Próxima prova: contagem em dias + as provas seguintes.
- Cronômetro: meta de 1h30 por tema, alarme em 2h, pausar/finalizar; cada sessão é salva.
- Horas na semana contra a meta semanal, barras por dia.
- Um card por disciplina: % do portal, selo da prova (data/hora ou "agendar até"), contadores x/y (conteúdos, exercícios, simulados, laboratório).
- Próxima ação sugerida (por regra: prova mais próxima × menor progresso × retestes pendentes).
- Linha do tempo de 14 dias (provas, prazos, eventos da agenda).
- % de acerto por tema (primeira nota e retestes), como medidor em linha com limiar em 70%; com 70% ou mais, mostra sucesso + ícone + "Aprendido".
- Blocos de estudo da agenda (lidos do Google Agenda).

**6.2 Agente (painel direito)**
- A partir de `lg`: terceira coluna da estrutura. Abaixo de `lg`: painel lateral (sheet) aberto por um botão na topbar ("Abrir agente"); o estado é mantido ao fechar.
- Checklist do dia: temas planejados + retestes do dia. Marcar uma tarefa conclui na hora (exceção E11 do DS).
- Campo de conversa: "cole o texto do tema ou pergunte algo". Enquanto o modelo local responde: "Pensando…", segundos depois de 5 s, Cancelar depois de 10 s; erros aparecem na própria lista com "Tentar de novo".
- Botões: Gerar questões, Revisar erros, Cronometrar.
- Estilo da prova: 10 questões de múltipla escolha por conjunto (e-book jan/2024). O número de alternativas por questão é uma configuração, ainda não se sabe (a confirmar numa prova ou simulado real).
- Ciclo central: texto do tema (colado ou lido do Notion) → resumo curto + 10 questões no estilo da prova → respondo sem consultar → o app corrige → as erradas vão para o registro de erros, cada uma com um campo opcional "minuto do vídeo" que eu preencho → resultados gravados de volta no Notion e no painel.
- Posso marcar uma questão ruim; questões marcadas não contam na nota.

**6.3 Medição de aprendizado**
- Tipos de tentativa: `first`, `retest_1d`, `retest_7d`, `retest_21d`. Retestes usam questões novas sobre o mesmo tema.
- Status do tema: `pendente` (sem reteste de 7 dias ainda), `aprendido` (reteste de 7 dias ≥ 70%), `revisar` (reteste de 7 dias < 70% → novo reteste em 3 dias).
- Horas aparecem só como contexto.

**6.4 Modo Gerenciar**
- Cadastro: graduações, semestres, disciplinas (com regra de avaliação), temas, provas, prazos.
- Digitação do progresso do portal por disciplina.
- Configurações: modelo padrão, meta de horas semanal, meta/alarme do cronômetro, IDs das páginas do Notion, ID da agenda.
- Tela do registro de uso (ver 7).

**6.5 ACC**
- Registro: atividade, categoria, horas, data, caminho do certificado (arquivo local), observações.
- Total exigido: 100h. Ponto de partida: as horas já computadas no histórico, lançadas como um registro inicial.
- Barra de progresso contra as 100h. Categorias, limites por categoria ou por atividade, prazo e comprovação: não se sabe — campos opcionais, preenchidos quando chegar o regulamento de AAC (ver 11).

**6.6 Progresso do curso**
- Total de horas, horas concluídas por componente e a data de referência vêm do histórico acadêmico.
- Componentes com horas concluídas/exigidas: mínima 1.040/2.860h; extensionistas 144/240h; AAC 16/100h (valores fictícios de demonstração); optativa 0/560h; estágio 0h (total exigido não registrado).
- A optativa não fecha a soma das 3.200h: aparece com a marca "a conferir" até a confirmação.
- As horas de cada disciplina contam no seu componente quando a disciplina é marcada como aprovada.

### 7. Engenharia de IA (controles de qualidade do agente)
- **Avaliação de modelos (fase 0):** pasta `eval/`. 3 temas reais × 2–3 modelos locais. Mede: taxa de JSON válido, tempo por resposta, minha nota de 1 a 5 para resumo e questões em português. Saída: `eval/RESULTS.md` com o modelo padrão escolhido e o porquê.
- **Saídas estruturadas:** toda chamada ao LLM devolve JSON validado contra um schema Pydantic (resumo, questões, alternativas, gabarito, explicação). JSON inválido → uma nova tentativa → erro na tela, nada salvo.
- **Prompts versionados:** os prompts ficam em `backend/prompts/*.md` no git; cada conjunto de questões guarda a versão do prompt e o modelo usado.
- **Registro de uso:** tabela `llm_call` (modelo, versão do prompt, tokens de entrada/saída, tempo, ok/erro), visível no modo Gerenciar.

### 8. Arquitetura
```
Navegador (localhost:8000)
   │
Docker: container do app (FastAPI serve a API + o React compilado)
   ├── SQLite ./data/painel.db (volume)
   ├── API do Notion (internet, token no .env)
   ├── API do Google Agenda (internet, token OAuth em ./secrets)
   └── LLM: http://host.docker.internal:11434/v1 (Ollama) ou :1234/v1 (LM Studio)
Windows: Ollama / LM Studio usando a GPU local
```
A verificar na fase 0: o container chegar ao Ollama do Windows sem expor o Ollama para a rede local.

### 9. Modelo de dados (inicial)
`degree`, `degree_component` (nome, horas exigidas, horas concluídas, a conferir), `semester`, `subject` (grading_rule em JSON, carga horária, componente, prova exige laboratório), `topic`, `exam`, `deadline`, `portal_progress`, `study_session`, `question_set` (tema, modelo, versão do prompt, tipo de tentativa), `question`, `answer`, `mistake` (questão, minuto do vídeo), `review_schedule`, `acc_activity`, `acc_rule`, `llm_call`, `setting`.

### 10. Segurança e privacidade
- Porta do app presa só a `127.0.0.1`.
- `.env` e `./secrets/` no `.gitignore`; nenhum token no código ou nos logs.
- A integração do Notion só vê as páginas que eu compartilho com ela.
- Agenda: nunca apagar; só editar eventos com `painel=1`.
- Cópia pública do portfólio: só dados mock, sem notas, sem dados reais do Notion ou da Agenda.
- Prints das minhas respostas vão só para o modelo local (D17), e só de páginas do Notion ligadas ou da pasta de materiais (D18).

### 11. Pendências
Pedidos ao chat da faculdade (prints do portal):
- Regulamento de AAC ou tela de AAC do portal (categorias, limites, prazo, comprovação).
- Matriz curricular completa, currículo 202202 (divisão das disciplinas pendentes por semestre, cargas horárias).
- Número de alternativas por questão (print de uma AV ou simulado anterior).
- Qual regra de nota vale hoje: e-book de jan/2024 ou planos de ensino de 2026.
- Calendário 2027.1 (início, provas, prazos de agendamento). Conhecido até agora: pré-matrícula de 22/10 a 25/11/2026.

### 12. Fases
| Fase | Conteúdo | Pronto quando |
|---|---|---|
| F0 | Repo, Docker, avaliação de modelos | `eval/RESULTS.md` define o modelo padrão |
| F1 | Base do backend, modelo de dados, cadastros do modo Gerenciar, progresso do portal, carga inicial (ver 13) | Consigo cadastrar o semestre atual e ver salvo |
| F2 | Estrutura do frontend com o DS + Painel (cards, próxima prova, cronômetro, horas, linha do tempo, próxima ação) | O painel mostra o semestre atual com os dados da carga inicial |
| F3 | Agente: resumo + questões, responder, corrigir, erros, seletor de modelo, registro de uso | Um ciclo completo de tema funciona de ponta a ponta |
| F4 | Retestes 1/7/21, status do tema, % por tema, Revisar erros | Um reteste aparece no dia certo e muda o status |
| F5 | Notion (ler texto do tema, gravar resultados) + Google Agenda (ler, criar/editar os próprios eventos) | Tema lido do Notion; prova criada na Agenda |
| F6 | Módulo de ACC | Horas de ACC acompanhadas contra o total |
| F7 | Cópia pública com dados mock + README | Repo público roda com dados mock |

A construção começa depois de 08/12/2026.

### 13. Carga inicial (F1)

Esta cópia pública vem com **dados fictícios** (`backend/app/seed.py`): uma graduação de exemplo, cinco disciplinas atuais com provas, progresso do portal, disciplinas pendentes e um registro inicial de ACC. Os dados reais ficam só na cópia privada do dono.

### 14. Versão 1.3 (12/11/2026, depois do primeiro uso real)
| # | Decisão |
|---|---|
| D13 | O modo Estudo ganha três páginas: **Painel**, **Provas e prazos** e **Histórico**. |
| D14 | **Provas e prazos** (lado Estudo): provas, prazos, eventos, laboratórios e atividades numa lista só; cada um pode ser editado e marcado como concluído. Laboratórios e atividades são prazos do tipo `lab` / `activity`. |
| D15 | **Histórico**: todo conjunto de questões fica salvo e visível (data, tipo, tema, nota), evolução por tema e três ações: refazer as questões erradas (sem chamar o modelo), novo teste com base nos meus erros, novo teste com base nos meus acertos. |
| D16 | **Simulado da prova**: um conjunto que mistura os temas de uma disciplina, do tamanho da prova real (configurações: 10 questões, 60 minutos), com contagem regressiva. Conta no histórico, não no ciclo de retestes do tema. |
| D17 | **Notas pelos prints**: o agente lê as imagens de uma página do Notion ligada a um tema, ou arquivos da pasta de materiais do curso (só leitura), com um **modelo local que lê imagens**. Regra: print só da resposta certa = acerto de primeira; cada print com resposta errada = uma tentativa errada. Nota = acertos de primeira ÷ total de questões × 10, mostrada junto com o total de tentativas erradas. O agente só **propõe**; nada é salvo antes de eu confirmar. |
| D18 | **Pasta de materiais**: só a pasta de materiais do curso definida no `.env` (`PAINEL_MATERIALS_HOST`), montada só para leitura no container. Nada mais do PC é lido. Imagens e PDFs agora; vídeos depois. |
| D19 | Edição no lado Estudo: renomear tarefas do checklist, editar temas, marcar prazos/eventos/labs como concluídos. |
| D20 | Card de resumo da semana (horas, conjuntos, nota média, temas aprendidos na semana) e backup automático diário do `painel.db` em `./data/backups` (guarda os últimos 14). |
| D21 | Rodapé: "© <ano> Painel de Estudos", links para GitHub e LinkedIn (definidos em Configurações) e "Site (em breve)" sem link. |
| D22 | **Versão futura (V3 a V5, não agora):** perguntar e dar comandos ao agente por voz, com limite de duração do áudio; voz para texto local, sem nuvem. Antes de construir, conferir os modelos suportados e o que é preciso. O agente responder em voz fica bem para depois. |

| Fase | Conteúdo | Pronto quando |
|---|---|---|
| F8 | D13–D21 | Um reteste continua no Histórico depois do F5 (recarregar a página); um lab é marcado como concluído; uma nota pelos prints é proposta e confirmada |

### 15. Versão 1.4 (12/11/2026)
| # | Decisão |
|---|---|
| D23 | **Faixa de 14 dias** como aprovada: duas linhas de 7 dias, contagens por tipo em cada dia (prova, prazo/lab/atividade/simulado, evento da agenda), clique no dia abre a lista com horários; itens feitos riscados. |
| D24 | **Sessões do cronômetro**: do primeiro Iniciar até Finalizar é uma sessão. Conta as pausas, soma os trechos estudados e guarda um relógio oculto do início ao fim (com as pausas). "Finalizar" fecha a sessão; toda sessão finalizada fica salva e aparece no Painel e em Desempenho. v1.7.2 (13/11/2026): "Zerar" virou "Cancelar", que descarta a sessão e os trechos depois de uma confirmação (as sessões "zeradas" antigas continuam). |
| D25 | Página **Desempenho** (modo Estudo): horas por dia, notas dos testes no tempo com a linha dos 70%, acerto, sequência de dias, números por disciplina (horas, testes, média, temas aprendidos, erros em aberto), foco no cronômetro (estudado ÷ total) e pausas, notas de provas/labs/simulados. Período de 7/30/90 dias. O agente lê um resumo desses números (só modelo local); autorizado por mim em 12/11/2026, ligado por padrão e dá para desligar em Configurações. |
| D26 | **Simulados** da faculdade: tipo próprio de prazo, `mock`; cada disciplina atual tem 2 (10 questões, até 1,0 ponto cada). Labs, atividades e simulados podem ligar a **própria página do Notion**, usada para ler os prints. |
| D27 | Links do rodapé nas cores oficiais das marcas. |

| Fase | Conteúdo | Pronto quando |
|---|---|---|
| F9 | D23–D27 | Uma sessão do cronômetro com 2 pausas é finalizada e aparece com tempo estudado, tempo total e pausas; a página própria do lab no Notion é lida |

### 16. Versão 1.5 (12/11/2026)
| # | Decisão |
|---|---|
| D28 | **Ciclo dos erros**: todo erro tem um status: não revisado → revisado ("Já revisei") → num refazer, acertou = corrigido, errou = revisar de novo. A cópia do refazer aponta para a questão original e atualiza o erro original; nunca cria erro novo. "Refazer erros não corrigidos" monta um conjunto (até 10, sem modelo) com os erros ainda não corrigidos, por tema, disciplina ou todos. Histórico, Desempenho e o resumo do agente mostram os erros por status. Os dados existentes foram convertidos (cópias do refazer juntadas ao erro original). |
| D29 | **Status do tema, regra "a"** (decidida por mim em 12/11/2026): o reteste de 7 dias decide o "aprendido"; um reteste de 21 dias abaixo de 70% manda o tema de volta para "revisar" (+ reteste em 3 dias). Refazer, testes de foco e simulados não mudam o status. |
| D30 | **Nota prevista** por disciplina no Painel, pela regra de avaliação (dado): parte da prova = melhor nota de prova, Progresso Acadêmico = soma dos simulados (simulado sem nota conta 0 por enquanto); mostra o total ou quanto falta na AV/AVS para passar. O resultado do simulado é em pontos (certas ÷ questões × 1,0); a nota da prova tem o teto da regra (ex.: AV/AVS de 0 a 8). O "feito" do laboratório em Provas e prazos decide o "lab pendente". |
| D31 | **Gráficos interativos** no Desempenho (passar o mouse/focar lê o valor, clicar na barra do dia mostra os trechos do cronômetro e os testes do dia, clicar numa nota abre o teste, filtro por disciplina); **confirmação** antes de marcar um item como feito em Provas e prazos; "Mandar provas para a agenda" lista as provas e manda só as marcadas; **conversa com o agente salva** (sobrevive ao recarregar, "Limpar conversa" com confirmação); o cronômetro liga à sessão uma pausa feita no primeiro segundo. |

| Fase | Conteúdo | Pronto quando |
|---|---|---|
| F10 | D28–D31 | Um refazer com 2 erradas deixa 2 "revisar de novo" e o resto "corrigido", sem erro novo; uma mensagem da conversa continua lá depois do F5; clicar numa nota no Desempenho abre aquele teste |

### 17. Versão 1.6 (12/11/2026): cards a partir dos meus pontos fracos
Aprovada por mim em 12/11/2026, com todas as recomendações do Claude.

| # | Decisão |
|---|---|
| D32 | **Cards dos meus pontos fracos.** Escolhidos por peso: erros "revisar de novo" > "não revisado" > temas em "Revisar" ou abaixo de 70% no último teste > erros "revisado"; empate vai para a disciplina com a prova mais próxima. Tipos: **conceito** (frente "o que é X?", verso em 1–2 linhas), **questão virada card** (de um erro: a pergunta sem as alternativas, verso = resposta certa e o porquê, mais o que eu marquei), **confusão** ("X vs Y", para erros em que marquei uma opção parecida). Todo card mostra onde rever: tema, página do Notion e o minuto do vídeo quando houver. Nunca dois cards do mesmo erro. |
| D33 | **Dois jeitos de responder.** **Virar:** lembro, viro e marco "Sabia" ou "Não sabia". **Responder:** 4 alternativas; as erradas vêm de erros que eu realmente cometi, quando existirem. Efeito no ciclo dos erros (D28) para cards que vieram de um erro: "Não sabia" ou resposta errada → "revisar de novo"; "Sabia" → "revisado" (se estava "não revisado"); acerto no Responder → "corrigido". Um card que eu sempre acerto passa do Responder para o Virar (lembrar é mais difícil). |
| D34 | **Geração.** "Gerar cards" por tema, por disciplina ou "meus pontos fracos"; 10 cards por geração por padrão. Fontes na C1: meus erros com as explicações, o texto do tema (`topic.source_text`) e o resumo do tema (que passa a ficar salvo). Prompt novo versionado `generate_cards.v1`, pelo cliente único de LLM (Pydantic, 1 nova tentativa, registro em `llm_call`). Só modelo local. |
| D35 | **Repetição.** Cada card tem o próprio calendário, com os intervalos do painel: card novo → 1 dia; "Sabia"/acerto → próximo passo (1 → 7 → 21 → 60 dias); "Não sabia"/erro → volta para 1 dia. Cards vencidos aparecem no "Montar o dia" e na "Próxima ação". |
| D36 | **Prints e vídeos como fonte.** Autorizado por mim em 12/11/2026: os prints das minhas respostas (labs, simulados, provas, atividades, de páginas do Notion ligadas ou da pasta de materiais) podem ser lidos **só pelo modelo local** para transcrever a questão e a resposta certa e transformar em cards (prompt novo `read_print_card.v1`). Vídeos só depois das fases de voz (V3 a V5), só local. Minhas notas nunca vão ao modelo como material de card. |
| D37 | **Onde aparece.** Página nova **Cards** no modo Estudo (gerar, uma linha por tema com total e vencidos hoje) e botão **Cards** no painel do agente (revisar um por vez). **Rodada rápida** (minigame): uns 10 cards em sequência dos meus pontos fracos, tempo por card opcional, contador de acertos seguidos, resultado curto no fim; sem pontos nem ranking. **Card do dia:** um card no Painel e no "Montar o dia", do ponto mais fraco da disciplina com a prova mais próxima. O Histórico mostra os cards por tema; o Desempenho pode mostrar cards revisados por dia. **Exportar para o Notion é opcional** (só acrescentar, nunca apagar). |

Dados: tabelas novas `card` (frente, verso, tipo, modo, tema, origem: erro/texto/print/vídeo, id da origem, alternativas, índice da certa, passo, próxima revisão, versão do prompt, criado em) e `card_review` (card, data, modo, sabia/acertou sim/não). Migração nova; o backup diário cobre.

| Fase | Conteúdo | Pronto quando |
|---|---|---|
| C1 | D32, D33, D34; revisão no painel do agente e página Cards | "Gerar cards dos meus pontos fracos" cria 10 cards dos meus erros e do texto do tema; respondo um no Virar e um no Responder, e o erro de origem muda de status como diz a D33 |
| C2 | D36 prints | Um lab com print errado gera um card com aquela questão e a resposta certa |
| C3 | D35, rodada rápida, card do dia, exportar para o Notion (opcional) | Um card marcado "Não sabia" vence de novo no dia seguinte; uma rodada rápida de 10 termina com o resultado; o card do dia aparece no Painel |
| C4 | D36 vídeos (depois das fases de voz) | Um card cita um trecho de vídeo transcrito localmente |

### 18. Versão 1.8 (13/11/2026): cursos e certificados
Aprovado por mim em 13/11/2026, com todas as recomendações do Claude (maquetes mostradas no chat). Cursos fora da faculdade (cursos livres, cursos com certificado, provas de certificação, idiomas, bootcamps) ganham uma área própria, sem misturar com a faculdade.

| # | Decisão |
|---|---|
| D38 | **Área separada.** A barra lateral do Estudo ganha dois grupos: **Faculdade** (Painel, Provas e prazos, Histórico, Cards, Desempenho, como hoje) e **Cursos e certificados** (Meus cursos, Histórico, Cards, Desempenho). As páginas da faculdade mostram só a faculdade (graduações do tipo `degree`); as de cursos, só os cursos. O Painel continua só com a faculdade. |
| D39 | **O curso reaproveita a hierarquia.** Curso = `degree` do tipo `course`, com: plataforma, tipo (curso com certificado, certificação com prova, idioma, bootcamp, curso livre), link, situação (quero fazer, fazendo, pausado, concluído), carga horária, início, meta de data, caminho do certificado (pasta de materiais), conta como AAC (+ categoria), página do Notion opcional, data da prova (certificações). Módulos = disciplinas sem semestre; aulas = temas. Questões, cards, cronômetro, histórico, gráficos e ciclo dos erros funcionam nos cursos como na faculdade. Progresso = módulos concluídos / total; sem módulos, um % manual. |
| D40 | **Plano do dia.** Os cursos não entram no "Montar o dia" (retestes e próximo passo) por padrão; uma chave em Configurações liga. Dentro do curso, o agente gera questões e cards como sempre. |
| D41 | **Horas.** As horas de curso contam separadas, com meta semanal própria (padrão 5 h, em Configurações). As horas e a meta da semana da faculdade não incluem os cursos. O cronômetro lista disciplinas da faculdade e módulos dos cursos em grupos separados. |
| D42 | **Provas de certificação** ficam só na área de cursos (página do curso e Meus cursos), não em Provas e prazos nem na faixa de 14 dias. |
| D43 | **Ponte com a AAC.** Ao concluir um curso que conta como AAC, "Lançar como AAC" cria a atividade de AAC já preenchida (título, categoria, horas, data, certificado) e liga ao curso, uma vez só; sem digitar duas vezes e sem contar em dobro. |
| D44 | **Notion.** Link opcional para uma página do Notion por curso (abrir a página); as aulas podem ligar páginas do Notion como os temas já fazem. Mesmas regras de hoje (nunca apagar). |

Dados: colunas novas em `degree` (platform, course_type, url, course_status, start_date, target_date, certificate_path, counts_acc, acc_category, notion_page_id, exam_at, manual_progress, acc_activity_id) e as configurações `course_weekly_goal_hours` e `courses_in_day_plan`. Migração nova; o backup diário cobre.

| Fase | Conteúdo | Pronto quando |
|---|---|---|
| K1 | D38, D39: grupos da barra lateral, Meus cursos (abas por situação, resumo, cards de curso), Novo curso | Crio um curso com 9 módulos; ele aparece em "Fazendo" com 0% e não aparece no Painel da faculdade |
| K2 | Página do curso: módulos e aulas, questões, cards e cronômetro por curso, D41, D42, D44 | Cronometro 20 min num módulo; conta em "Horas em cursos" e não na semana da faculdade; um teste numa aula aparece só em Cursos › Histórico |
| K3 | Cursos › Histórico, Cards, Desempenho; chave do D40; ponte do D43 com a AAC | Um curso concluído que conta como AAC cria uma atividade de AAC com as horas dele, e o botão some |
