# CLAUDE.md — Painel de Estudos

Bilingual file (DIRETRIZ_BILINGUE_v1): English first, Portuguese after. If they differ, the Portuguese prevails.

---

## ENGLISH

### What this project is
A local study panel + local study agent for its owner. Full scope, decisions and phases: `SPEC.md`. Read it before any task. If a request conflicts with `SPEC.md`, stop and ask.

### How to work
1. Confirm decisions before coding. If a task needs a choice that `SPEC.md` doesn't settle, ask first and wait.
2. One phase at a time (F0 → F7). Don't start the next phase without the owner's OK.
3. Scope guard: build only what `SPEC.md` lists. Ideas outside it go to an ideas list (e.g. `docs/IDEIAS.md`), not into code.
4. Before changing or deleting any existing file, list what will change and wait for the OK.
5. Answers to the owner: bilingual, English first, then Portuguese with the same content.
6. Code comments: Portuguese (pt-BR). Identifiers in English.
7. Commits: 100% English (subject and body). Push only to `claude/*` branches, one pull request per phase; merging into `main` is the owner's.
8. After each phase: run the app, check the "done when" line of the phase, report what was verified and how.

### Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy, Pydantic, SQLite at `./data/painel.db`.
- Frontend: React + Vite + TypeScript + Tailwind v4, own design system (design pattern), Application surface.
- LLM: OpenAI-compatible API. Ollama `http://host.docker.internal:11434/v1` (default), LM Studio `:1234/v1`. Model list comes from the server; never hard-code a model name outside settings.
- Run: `docker compose up` → `http://localhost:8000`. Port bound to `127.0.0.1`.

### Design System rules
- The design pattern (DS) is the only source of visual decisions. Its tokens are in `frontend/src/styles/ds-tokens.css` and `index.css`; the full briefing is not part of this repository.
- Colors: only the primary family is custom, in the panel's own `tema.css`, with the values in `SPEC.md` D5 (allowed by DS v2.13; AA already checked by the DS). Everything else is the DS default.
- `--primary` is background only. Any text in the primary color uses `--primary-text` (`text-primary-text`).
- Inline style only for geometry that changes at runtime (meter fill, threshold, timer progress), via a custom property (e.g. `style={{ '--value': '60%' }}`).
- The panel patterns (timer ring, 14-day strip, inline meter, right panel, chat, daily checklist, question card, subject card, mode switch) follow the DS; reuse the existing components instead of creating new ones.
- Do not invent tokens, colors, spacing, components or patterns. Anything the DS does not cover is a DS change, not an improvisation in the panel.

### AI rules
- Every LLM call goes through one client module that: validates JSON with a Pydantic schema, retries once, logs to `llm_call` (model, prompt version, tokens, latency, status).
- Prompts live in `backend/prompts/*.md` with a version header. Changing a prompt = new version; never edit a released version in place.
- Never send personal data (grades, names, calendar) to the model. Only topic text and questions.
- No cloud LLMs (Claude, Gemini, OpenAI) in the app.

### Integration rules
- Google Calendar: **never delete events.** Create and edit only; edit only events with private extended property `painel=1`.
- Notion: read/write only pages shared with the integration; never delete pages or blocks — append or update.
- Tokens only in `.env` and `./secrets/` (both in `.gitignore`). Never print tokens in logs or answers.

### Data
- Real data stays local (`./data`, `./secrets`). The public portfolio copy (F7) uses mock data only.
- Grading rules are data (`subject.grading_rule`), never `if` statements per subject.

---

## PORTUGUÊS

### O que é este projeto
Um painel de estudos local + agente de estudos local para o dono. Escopo completo, decisões e fases: `SPEC.md`. Leia antes de qualquer tarefa. Se um pedido conflitar com o `SPEC.md`, pare e pergunte.

### Como trabalhar
1. Confirmar decisões antes de codar. Se uma tarefa exige uma escolha que o `SPEC.md` não define, pergunte antes e espere.
2. Uma fase por vez (F0 → F7). Não começar a próxima fase sem o OK do dono.
3. Guarda de escopo: construir só o que o `SPEC.md` lista. Ideias fora dele vão para uma lista de ideias (ex.: `docs/IDEIAS.md`), não para o código.
4. Antes de alterar ou apagar qualquer arquivo existente, listar o que vai mudar e esperar o OK.
5. Respostas ao dono: bilíngues, inglês primeiro, depois português com o mesmo conteúdo.
6. Comentários de código: português (pt-BR). Identificadores em inglês.
7. Commits: 100% em inglês (assunto e corpo). Push só em branches `claude/*`, um pull request por fase; o merge no `main` é do dono.
8. Ao fim de cada fase: rodar o app, conferir a linha "pronto quando" da fase e relatar o que foi verificado e como.

### Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy, Pydantic, SQLite em `./data/painel.db`.
- Frontend: React + Vite + TypeScript + Tailwind v4, padrão de design próprio, superfície Aplicação.
- LLM: API compatível com OpenAI. Ollama `http://host.docker.internal:11434/v1` (padrão), LM Studio `:1234/v1`. A lista de modelos vem do servidor; nunca fixar nome de modelo fora das configurações.
- Rodar: `docker compose up` → `http://localhost:8000`. Porta presa a `127.0.0.1`.

### Regras do Design System
- O padrão de design (DS) é a única fonte de decisões visuais. Os tokens estão em `frontend/src/styles/ds-tokens.css` e `index.css`; o briefing completo não faz parte deste repositório.
- Cores: só a família primary é própria, no `tema.css` do painel, com os valores do `SPEC.md` D5 (permitido pelo DS v2.13; AA já conferido pelo DS). Todo o resto é o padrão do DS.
- `--primary` é só fundo. Todo texto na cor primária usa `--primary-text` (`text-primary-text`).
- Style inline só para geometria que muda em execução (preenchimento do medidor, limiar, progresso do cronômetro), por custom property (ex.: `style={{ '--value': '60%' }}`).
- Os padrões do painel (anel do cronômetro, faixa de 14 dias, medidor em linha, painel direito, conversa, checklist do dia, card de questão, card de disciplina, seletor de modo) seguem o DS; reaproveite os componentes que já existem em vez de criar novos.
- Não inventar tokens, cores, espaçamentos, componentes ou padrões. O que o DS não cobre é uma mudança no DS, não um improviso no painel.

### Regras de IA
- Toda chamada ao LLM passa por um único módulo cliente que: valida o JSON com schema Pydantic, tenta de novo uma vez, registra em `llm_call` (modelo, versão do prompt, tokens, tempo, status).
- Os prompts ficam em `backend/prompts/*.md` com cabeçalho de versão. Mudar um prompt = nova versão; nunca editar uma versão já usada.
- Nunca mandar dados pessoais (notas, nomes, agenda) ao modelo. Só texto do tema e questões.
- Nenhum LLM em nuvem (Claude, Gemini, OpenAI) no app.

### Regras das integrações
- Google Agenda: **nunca apagar eventos.** Só criar e editar; editar só eventos com a propriedade estendida privada `painel=1`.
- Notion: ler/gravar só páginas compartilhadas com a integração; nunca apagar páginas ou blocos — acrescentar ou atualizar.
- Tokens só no `.env` e em `./secrets/` (os dois no `.gitignore`). Nunca imprimir tokens em logs ou respostas.

### Dados
- Dados reais ficam locais (`./data`, `./secrets`). A cópia pública do portfólio (F7) usa só dados mock.
- Regras de avaliação são dados (`subject.grading_rule`), nunca `if` por disciplina.
