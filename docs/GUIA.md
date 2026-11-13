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
- **Painel (Estudo):** next exam, hours this week, suggested next action, study timer, subject cards (portal progress, counters and the **predicted grade**: what you already have and how much you need in the AV/AVS to pass, by the subject's grading rule), % per topic and the next 14 days (click a day to see its list with times).
- **Timer:** choose the subject → Iniciar. Each pause saves the stretch you studied. **Finalizar** closes the session (studied time, total time with pauses, number of pauses); Zerar discards the clock but keeps what was saved. Goal 1h30 per topic, alarm at 2h (Configurações).
- **Hoje (agent panel):** "Montar o dia" adds due retests and the next study step. Checking an item completes it at once; the pencil renames it, the trash can removes it.
- **Gerar questões:** choose subject and topic, paste **one module at a time** (up to 30,000 characters, counter under the field), choose the number of alternatives, "Gerar resumo e questões". Answer without looking things up; at the end you get the % and the points to rewatch.
- **Retests:** after the first set of a topic the panel schedules retests at 1, 7 and 21 days. The 7-day retest decides: 70% or more = learned; below = review + new retest in 3 days. If the 21-day retest is below 70%, the topic goes back to review. Redo, focus tests and mock exams don't change the status. Due retests show up first in "Próxima ação" and in "Montar o dia".
- **Revisar erros (mistake cycle):** every wrong answer has a status: **Não revisado** → "Já revisei" → **Revisado** → in a redo, right = **Corrigido**, wrong = **Revisar de novo**. "Refazer erros não corrigidos" builds a set with up to 10 of them (no model, instant). Redoing never creates new mistakes; it updates the original ones. "Marcar questão ruim" removes a bad question from the score.
- **Conversa:** ask about the topic in the field at the bottom of the agent panel. The conversation is saved (it comes back after reloading the page); "Limpar conversa" erases only the messages. If allowed in Configurações, the agent also reads a short summary of your study numbers (local model only).
- **Provas e prazos (Estudo):** exams, deadlines, labs, activities and the college's mock exams in one list. Ticking the box asks for confirmation before marking as done. **Resultado** reads the prints (Notion page of the item or of the topic, or a folder in the materials folder) and proposes the score; you confirm. A mock exam is worth up to 1.0 point (right answers ÷ questions); the exam follows the subject rule (e.g. AV/AVS 0–8).
- **Histórico:** every test stays saved: evolution per topic (click a score to open the test), mistakes per status, "Refazer erros", "Novo teste: erros/acertos", "Refazer erradas" per test and the timed **Simulado da prova**.
- **Cards (Estudo › Cards):** cards made from what you get wrong most. "Gerar cards dos meus pontos fracos" makes 10 with the local model (unfixed mistakes first, then topics below 70%); "De prints ou de vídeo" makes cards from the prints of a topic (Notion or materials folder) or from a video transcript (a `.vtt`, `.srt` or `.txt` file next to the video, or pasted). Answer each card with 4 alternatives (**Responder**) or recall and flip (**Virar**): a card from a mistake updates that mistake (wrong → "revisar de novo", right → "corrigido"). Each card comes back after 1, 7, 21 and 60 days; "Não sabia" sends it back to 1 day. **Rodada rápida** = 10 cards in a row with time and streak; the **card do dia** is on the Painel; due cards show in "Próxima ação" and "Montar o dia". "Notion" appends the topic's cards to its page (never deletes).
- **Desempenho:** hours per day and test scores with the 70% line, filtered by period and subject. Hover or tap a bar or a point to read it; click a bar to see what you did that day; click a point to open that test. Also KPIs, per-subject numbers, timer sessions and the scores of exams, labs and mocks.
- **Gerenciar → Disciplinas e temas:** subjects, grading rule, portal progress and topics ("Concluído no portal").
- **Semestres e curso** (course progress), **Atividades complementares** (ACC hours against the total), **Configurações** (goals, model, image-reading test, footer links, agent reading the numbers, integrations, usage log). "Mandar provas para a agenda" lists the exams first; only the ones you tick are sent (leave unticked the ones already in your calendar).

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
- **Painel (Estudo):** próxima prova, horas na semana, próxima ação sugerida, cronômetro, cards das disciplinas (progresso do portal, contadores e a **nota prevista**: o que você já tem e quanto falta na AV/AVS para passar, pela regra de avaliação da disciplina), % por tema e os próximos 14 dias (clique num dia para ver a lista com horários).
- **Cronômetro:** escolha a disciplina → Iniciar. Cada pausa salva o trecho estudado. **Finalizar** fecha a sessão (tempo estudado, tempo total com as pausas e número de pausas); Zerar descarta o relógio mas mantém o que já foi salvo. Meta de 1h30 por tema, alarme em 2h (Configurações).
- **Hoje (painel do agente):** "Montar o dia" coloca os retestes vencidos e o próximo passo de estudo. Marcar um item conclui na hora; o lápis renomeia e a lixeira remove.
- **Gerar questões:** escolha disciplina e tema, cole **um módulo por vez** (até 30.000 caracteres, contador embaixo do campo), escolha o número de alternativas, "Gerar resumo e questões". Responda sem consultar; no fim aparece o % e os pontos para rever no vídeo.
- **Retestes:** depois do primeiro conjunto de um tema, o painel agenda retestes em 1, 7 e 21 dias. O de 7 dias decide: 70% ou mais = aprendido; abaixo = revisar + novo reteste em 3 dias. Se o reteste de 21 dias ficar abaixo de 70%, o tema volta para revisar. Refazer, testes de foco e simulados não mudam o status. Retestes vencidos aparecem primeiro na "Próxima ação" e no "Montar o dia".
- **Revisar erros (ciclo dos erros):** cada resposta errada tem um status: **Não revisado** → "Já revisei" → **Revisado** → num refazer, acertou = **Corrigido**, errou = **Revisar de novo**. "Refazer erros não corrigidos" monta um conjunto com até 10 deles (sem modelo, na hora). Refazer nunca cria erro novo; atualiza o erro original. "Marcar questão ruim" tira uma questão ruim da nota.
- **Conversa com o Burro bot (o agente):** pergunte sobre o tema no campo embaixo do painel do agente. A conversa fica salva (volta depois de recarregar a página); "Limpar conversa" apaga só as mensagens. Se liberado em Configurações, o agente também lê um resumo curto dos seus números de estudo (só modelo local).
- **Provas e prazos (Estudo):** provas, prazos, laboratórios, atividades e os simulados da faculdade numa lista só. Marcar a caixa pede confirmação antes de dar como feito. **Resultado** lê os prints (página do Notion do item ou do tema, ou uma pasta da pasta de materiais) e propõe a nota; você confirma. O simulado vale até 1,0 ponto (certas ÷ questões); a prova segue a regra da disciplina (ex.: AV/AVS de 0 a 8).
- **Histórico:** todo teste fica salvo: evolução por tema (clique numa nota para abrir o teste), erros por status, "Refazer erros", "Novo teste: erros/acertos", "Refazer erradas" por teste e o **Simulado da prova** com tempo.
- **Cards (Estudo › Cards):** cards feitos a partir do que você mais erra. "Gerar cards dos meus pontos fracos" faz 10 com o modelo local (primeiro os erros não corrigidos, depois os temas abaixo de 70%); "De prints ou de vídeo" faz cards a partir dos prints de um tema (Notion ou pasta de materiais) ou da transcrição de um vídeo (arquivo `.vtt`, `.srt` ou `.txt` ao lado do vídeo, ou colada). Responda cada card com 4 alternativas (**Responder**) ou lembre e vire (**Virar**): um card que veio de um erro atualiza esse erro (errou → "revisar de novo", acertou → "corrigido"). Cada card volta depois de 1, 7, 21 e 60 dias; "Não sabia" volta para 1 dia. **Rodada rápida** = 10 cards seguidos com tempo e sequência; o **card do dia** fica no Painel; os cards vencidos aparecem na "Próxima ação" e no "Montar o dia". "Notion" acrescenta os cards do tema na página dele (nunca apaga).
- **Desempenho:** horas por dia e notas dos testes com a linha dos 70%, filtrados por período e disciplina. Passe o mouse ou toque numa barra ou num ponto para ler; clique numa barra para ver o que fez naquele dia; clique num ponto para abrir aquele teste. Também os números do período, os números por disciplina, as sessões do cronômetro e as notas de provas, labs e simulados.
- **Gerenciar → Disciplinas e temas:** disciplinas, regra de avaliação, progresso do portal e temas ("Concluído no portal").
- **Semestres e curso** (progresso do curso), **Atividades complementares** (horas de ACC contra o total), **Configurações** (metas, modelo, teste de leitura de imagem, links do rodapé, agente lendo os números, integrações, registro de uso). "Mandar provas para a agenda" lista as provas antes; só vão as que você marcar (deixe desmarcadas as que já estão na sua agenda).

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
