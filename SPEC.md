# SPEC — Painel de Estudos (painel-de-estudos)

Version 1.2 · 09/11/2026 · Owner: (seu nome aqui) · Builder: Claude Code
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
- Padrões de Projetos com Java: AV/AVS 0–10, in person, 75% attendance.
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
- Padrões de Projetos com Java: AV/AVS 0–10, presencial, 75% de frequência.
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
