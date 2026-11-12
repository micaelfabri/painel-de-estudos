# Guia do Painel de Estudos / Painel de Estudos guide

Bilingual file (DIRETRIZ_BILINGUE_v1): English first, Portuguese after. If they differ, the Portuguese prevails. The PDF version (`docs/guia/GUIA.pdf`) carries the Portuguese section with screenshots. Inside the app: Gerenciar → Como usar.

## ENGLISH

### 1. What it is
A study panel that runs only on your PC. Docker serves the app at `http://localhost:8000`; a local model (LM Studio or Ollama) writes summaries and questions. Nothing goes to the cloud. Your data lives in the `data` folder of the project.

### 2. Every day: turn it on and off
1. Open **Docker Desktop** and wait for "Engine running".
2. Open **LM Studio** → Developer → Local Server → **Status: Running**.
3. In PowerShell, in the project folder: `docker compose up`
4. Open **http://localhost:8000** in the browser. (`0.0.0.0:8000` in the log is internal to Docker and never opens in the browser.)
5. To turn off: `Ctrl + C` in PowerShell. Closing LM Studio frees the video card.

### 3. LM Studio, once
1. Local Server → **Server Settings** → turn on **Serve on Local Network** (Docker can only reach LM Studio this way).
2. In the same window, keep **Just-in-Time model loading** on.
3. Library → gear icon of each model → **Context Length 16384** and **thinking/reasoning off**. Then Eject the model so it reloads.
4. In the panel: Gerenciar → Configurações → "Endereço do modelo local" = `http://host.docker.internal:1234/v1`, Salvar, reload the page (F5), pick the **Modelo padrão**, Salvar again.

### 4. Updating after a new pull request
1. On GitHub: open the PR → **Merge pull request** → "Create a merge commit".
2. In PowerShell: `git checkout main`, `git pull`, `docker compose up --build`.

Your data stays (it is in `data`, outside the code).

### 5. Using it
- **Painel (Estudo):** next exam, hours this week, suggested next action, study timer, subject cards, % per topic and the next 14 days.
- **Timer:** choose the subject → Iniciar. Each pause saves the stretch you studied. Goal 1h30 per topic, alarm at 2h (Configurações).
- **Hoje (agent panel):** "Montar o dia" adds due retests and the next study step. Checking an item completes it at once.
- **Gerar questões:** choose subject and topic, paste **one module at a time** (up to 30,000 characters, counter under the field), choose the number of alternatives, "Gerar resumo e questões". Answer without looking things up; at the end you get the % and the points to rewatch.
- **Retests:** after the first set of a topic the panel schedules retests at 1, 7 and 21 days. The 7-day retest decides: 70% or more = learned; below = review + new retest in 3 days. Due retests show up first in "Próxima ação" and in "Montar o dia".
- **Revisar erros:** every wrong answer, with the right one and the explanation. "Marcar como revisado" when done. "Marcar questão ruim" removes a bad question from the score.
- **Conversa:** ask about the topic in the field at the bottom of the agent panel.
- **Gerenciar → Disciplinas e temas:** subjects, grading rule, portal progress and topics ("Concluído no portal").
- **Provas e prazos**, **Semestres e curso** (course progress), **Atividades complementares** (ACC hours against the total), **Configurações** (goals, model, usage log).

### 6. Model test (F0)
Picks the default model with your own course text. Steps in `eval/README.md`: paste 3 modules into `eval/topics/*.txt`, run one Docker command, rate the answers 1–5.

### 7. Credentials for F5 (Notion and Google Calendar)
You create them; they never go to GitHub. F5 will read:

- `NOTION_TOKEN=...` in the `.env` file (project root).
- `secrets/google_client.json` (the downloaded Google file).

**Notion**

1. You must be the workspace owner. In Notion: Settings → **Developer** (Desenvolvedor) → **Open developer tools ↗** (Abrir ferramentas do desenvolvedor). Do **not** use "Personal access tokens (PATs)" / "Novo token": a PAT sees everything your account sees.
2. **New connection** (Nova conexão): name "Painel de Estudos", authentication method **API token** (Token de API), not OAuth → **Create connection** (Criar conexão).
3. Capabilities: **read content**, **update content**, **insert content**. Copy the token and paste it in the `.env` file (project root) as `NOTION_TOKEN=<token>`. Never paste it in a chat or in `.env.example`, and never commit it.
4. Give access: open each study page in Notion → **•••** (top right) → **Connections** (Conexões) → add "Painel de Estudos" → confirm. Child pages are included. Without this, the API sees nothing.

**Google Calendar**

1. Go to console.cloud.google.com, create a project "Painel de Estudos".
2. APIs & Services → Library → **Google Calendar API** → **Enable**.
3. Menu → **Google Auth platform** → **Get started**: app name "Painel de Estudos", your e-mail; Audience **External**; contact e-mail; accept the policy → **Create**.
4. Google Auth platform → **Audience** → **Test users** → **Add users** → your Gmail.
5. Google Auth platform → **Clients** → **Create client** → type **Desktop app** → name "Painel" → **Create** → **Download JSON**. Save it as `secrets/google_client.json`.
6. To stop signing in every ~7 days, publish the app (Audience → Publish app). Google then asks for a public home page and a privacy policy in Branding; host two simple static pages anywhere (e.g. Vercel) describing the app and the scopes it uses. Until then the app stays in **Testing** and the panel asks for **Conectar Google** about every 7 days.
7. Create the `secrets` folder in the project and put the file there. Then in the panel: Gerenciar → Configurações → Integrações → **Conectar Google** → sign in → allow. On the "Google hasn't verified this app" screen: Advanced → continue (it is your own app).

After signing in, the token stays in `secrets/google_token.json`. **Mandar provas para a agenda** creates the "Painel de Estudos" calendar and the exam events; your calendar events show up in the 14-day strip.

### 8. Problems
| What you see | What to do |
|---|---|
| `0.0.0.0:8000` does not open | Use `http://localhost:8000`. |
| "Modelo local fora do ar" | LM Studio server off, or "Serve on Local Network" off, or wrong address in Configurações. |
| "Nenhum modelo em …" | The address points to Ollama with no models. Use LM Studio's address. |
| "A resposta do modelo foi cortada" | Context Length 16384 and thinking off; or paste a smaller part. |
| "Texto longo demais" | Paste one module at a time (counter under the field). |
| Very slow / PC freezing | Smaller model (gemma-4-E4B), close games and heavy apps, thinking off. |
| `port is already allocated` | Another copy is running: `docker compose down`, then `up` again. |

### 9. Backup
Copy the `data` folder somewhere safe (HD, Drive). To restore: stop the app and put the folder back.

---

## PORTUGUÊS

### 1. O que é
Um painel de estudos que roda só no seu PC. O Docker serve o app em `http://localhost:8000`; um modelo local (LM Studio ou Ollama) escreve resumos e questões. Nada vai para a nuvem. Seus dados ficam na pasta `data` do projeto.

### 2. Todo dia: ligar e desligar
1. Abra o **Docker Desktop** e espere aparecer "Engine running".
2. Abra o **LM Studio** → Developer → Local Server → **Status: Running**.
3. No PowerShell, na pasta do projeto: `docker compose up`
4. Abra **http://localhost:8000** no navegador. (O `0.0.0.0:8000` do log é interno do Docker e nunca abre no navegador.)
5. Para desligar: `Ctrl + C` no PowerShell. Fechar o LM Studio libera a placa de vídeo.

### 3. LM Studio, uma vez só
1. Local Server → **Server Settings** → ligar **Serve on Local Network** (só assim o Docker alcança o LM Studio).
2. Na mesma janela, deixar **Just-in-Time model loading** ligado.
3. Library → engrenagem de cada modelo → **Context Length 16384** e **thinking/raciocínio desligado**. Depois Eject no modelo para ele recarregar.
4. No painel: Gerenciar → Configurações → "Endereço do modelo local" = `http://host.docker.internal:1234/v1`, Salvar, recarregar a página (F5), escolher o **Modelo padrão**, Salvar de novo.

### 4. Atualizar depois de um pull request novo
1. No GitHub: abrir o PR → **Merge pull request** → "Create a merge commit".
2. No PowerShell: `git checkout main`, `git pull`, `docker compose up --build`.

Seus dados continuam (ficam em `data`, fora do código).

### 5. Usando
- **Painel (Estudo):** próxima prova, horas na semana, próxima ação sugerida, cronômetro, cards das disciplinas, % por tema e os próximos 14 dias.
- **Cronômetro:** escolha a disciplina → Iniciar. Cada pausa salva o trecho estudado. Meta de 1h30 por tema, alarme em 2h (Configurações).
- **Hoje (painel do agente):** "Montar o dia" coloca os retestes vencidos e o próximo passo de estudo. Marcar um item conclui na hora.
- **Gerar questões:** escolha disciplina e tema, cole **um módulo por vez** (até 30.000 caracteres, contador embaixo do campo), escolha o número de alternativas, "Gerar resumo e questões". Responda sem consultar; no fim aparece o % e os pontos para rever no vídeo.
- **Retestes:** depois do primeiro conjunto de um tema, o painel agenda retestes em 1, 7 e 21 dias. O de 7 dias decide: 70% ou mais = aprendido; abaixo = revisar + novo reteste em 3 dias. Retestes vencidos aparecem primeiro na "Próxima ação" e no "Montar o dia".
- **Revisar erros:** cada resposta errada, com a certa e a explicação. "Marcar como revisado" quando terminar. "Marcar questão ruim" tira uma questão ruim da nota.
- **Conversa:** pergunte sobre o tema no campo embaixo do painel do agente.
- **Gerenciar → Disciplinas e temas:** disciplinas, regra de avaliação, progresso do portal e temas ("Concluído no portal").
- **Provas e prazos**, **Semestres e curso** (progresso do curso), **Atividades complementares** (horas de ACC contra o total), **Configurações** (metas, modelo, registro de uso).

### 6. Teste de modelos (F0)
Escolhe o modelo padrão com o texto das suas matérias. Passos no `eval/README.md`: colar 3 módulos em `eval/topics/*.txt`, rodar um comando do Docker, dar notas de 1 a 5 às respostas.

### 7. Credenciais para a F5 (Notion e Google Agenda)
Você cria; elas nunca vão para o GitHub. A F5 vai ler:

- `NOTION_TOKEN=...` no arquivo `.env` (raiz do projeto).
- `secrets/google_client.json` (o arquivo baixado do Google).

**Notion**

1. Você precisa ser o dono do workspace. No Notion: Configurações → **Desenvolvedor** → **Abrir ferramentas do desenvolvedor ↗**. **Não** use "Tokens de acesso individual (PATs)" / "Novo token": um PAT enxerga tudo o que a sua conta enxerga.
2. **Nova conexão**: nome "Painel de Estudos", método de autenticação **Token de API** (não OAuth) → **Criar conexão**.
3. Capacidades: **ler conteúdo**, **atualizar conteúdo**, **inserir conteúdo**. Copie o token e cole no arquivo `.env` (raiz do projeto) como `NOTION_TOKEN=<token>`. Nunca cole em chat nem no `.env.example`, e nunca faça commit.
4. Dar acesso: abra cada página de estudo no Notion → **•••** (canto superior direito) → **Conexões** → adicionar "Painel de Estudos" → confirmar. As páginas filhas entram junto. Sem isso, a API não enxerga nada.

**Google Agenda**

1. Entre em console.cloud.google.com e crie um projeto "Painel de Estudos".
2. APIs e serviços → Biblioteca → **Google Calendar API** → **Ativar**.
3. Menu → **Google Auth platform** → **Get started** (Começar): nome do app "Painel de Estudos", seu e-mail; Audience (Público) **External** (Externo); e-mail de contato; aceitar a política → **Create** (Criar).
4. Google Auth platform → **Audience** → **Test users** → **Add users** → seu Gmail.
5. Google Auth platform → **Clients** → **Create client** → tipo **Desktop app** (App para computador) → nome "Painel" → **Create** → **Download JSON**. Salve como `secrets/google_client.json`.
6. Para não precisar logar a cada ~7 dias, publique o app (Público-alvo → Publicar app). O Google pede então uma página inicial e uma política de privacidade públicas no Branding; publique duas páginas estáticas simples em qualquer lugar (ex.: Vercel) descrevendo o app e os escopos usados. Até lá, o app fica em **Testando** e o painel pede **Conectar Google** a cada ~7 dias.
7. Crie a pasta `secrets` no projeto e coloque o arquivo lá. Depois, no painel: Gerenciar → Configurações → Integrações → **Conectar Google** → entrar → permitir. Na tela "O Google não verificou este app": Avançado → continuar (o app é seu).

Depois do login, o token fica em `secrets/google_token.json`. **Mandar provas para a agenda** cria a agenda "Painel de Estudos" e os eventos das provas; os eventos da sua agenda aparecem na faixa de 14 dias.

### 8. Problemas
| O que aparece | O que fazer |
|---|---|
| `0.0.0.0:8000` não abre | Use `http://localhost:8000`. |
| "Modelo local fora do ar" | Servidor do LM Studio desligado, ou "Serve on Local Network" desligado, ou endereço errado em Configurações. |
| "Nenhum modelo em …" | O endereço aponta para o Ollama sem modelos. Use o endereço do LM Studio. |
| "A resposta do modelo foi cortada" | Context Length 16384 e raciocínio desligado; ou cole um trecho menor. |
| "Texto longo demais" | Cole um módulo por vez (contador embaixo do campo). |
| Muito lento / PC travando | Modelo menor (gemma-4-E4B), feche jogos e apps pesados, raciocínio desligado. |
| `port is already allocated` | Outra cópia está rodando: `docker compose down` e depois `up` de novo. |

### 9. Backup
Copie a pasta `data` para um lugar seguro (HD, Drive). Para restaurar: desligue o app e coloque a pasta de volta.
