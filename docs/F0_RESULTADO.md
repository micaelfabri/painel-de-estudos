# F0 — resultado do teste de modelos / model test result

Bilingual file (DIRETRIZ_BILINGUE_v1): English first, Portuguese after. If they differ, the Portuguese prevails.

## ENGLISH

**Run:** 10/11/2026 on the owner's PC (8 GB GPU, LM Studio, context 16384, reasoning budget 0), 5 modules of a security course (15–23k characters), 10 questions × 5 alternatives each, one model loaded at a time. Raw reports stay on the PC (`eval/RESULTS_2026-11-10_*.md`, ignored by git because they hold text derived from the course material).

| Model | Valid sets | Avg time per set | Tokens out | Followed the format? | Suggested rating (1–5) |
|---|---|---|---|---|---|
| google/gemma-4-26b-a4b-qat | 5/5 | ~2 min 50 s | 1.7–2.0k | Yes: 50 questions, all with 5 alternatives | **5** — most plausible distractors and clearest statements |
| google/gemma-4-12b-qat | 5/5 | ~4 min 20 s | 1.8–2.0k | Yes | **4** — good quality, but the slowest (close to the old 300 s limit) |
| google/gemma-4-e4b | 5/5 | ~47 s | 1.6–2.0k | No: 46 questions (one set came short) | **4** — fast and correct, some distractors too obvious |
| qwen/qwen3.5-9b | 5/5 | ~70 s | 1.4–1.8k | No: 10 questions with 4 alternatives; correct answer at A in 82% of questions | **3** — content right, but the answer position gives it away |

Checked by sampling the same module across the 4 models: correct answers matched the text in all samples; no repeated questions in any set.

**Fixes that came out of F0 (PR "Exact question format and shuffled options"):** the panel now requires exactly N questions with N alternatives (sent as JSON schema, so LM Studio enforces it), and it shuffles the alternatives, so no model can concentrate the right answer on one letter.

**Recommendation:** default model `google/gemma-4-26b-a4b-qat` (best quality, under 3 minutes). If 3 minutes per set feels slow, `google/gemma-4-e4b` is the fast option (~47 s). **Decision: the owner's** (Gerenciar → Configurações → Modelo padrão).

## PORTUGUÊS

**Rodada:** 10/11/2026 no PC do dono (GPU de 8 GB, LM Studio, contexto 16384, reasoning budget 0), 5 módulos de uma disciplina de segurança (15–23 mil caracteres), 10 questões × 5 alternativas cada, um modelo carregado por vez. Os relatórios brutos ficam no PC (`eval/RESULTS_2026-11-10_*.md`, ignorados pelo git porque têm texto derivado do material das matérias).

| Modelo | Conjuntos válidos | Tempo médio por conjunto | Tokens de saída | Seguiu o formato? | Nota sugerida (1–5) |
|---|---|---|---|---|---|
| google/gemma-4-26b-a4b-qat | 5/5 | ~2 min 50 s | 1,7–2,0 mil | Sim: 50 questões, todas com 5 alternativas | **5** — distratores mais plausíveis e enunciados mais claros |
| google/gemma-4-12b-qat | 5/5 | ~4 min 20 s | 1,8–2,0 mil | Sim | **4** — boa qualidade, mas o mais lento (perto do antigo limite de 300 s) |
| google/gemma-4-e4b | 5/5 | ~47 s | 1,6–2,0 mil | Não: 46 questões (um conjunto veio incompleto) | **4** — rápido e correto, alguns distratores óbvios demais |
| qwen/qwen3.5-9b | 5/5 | ~70 s | 1,4–1,8 mil | Não: 10 questões com 4 alternativas; resposta certa na letra A em 82% das questões | **3** — conteúdo certo, mas a posição da resposta entrega |

Conferido por amostragem do mesmo módulo nos 4 modelos: as respostas certas batiam com o texto em todas as amostras; nenhuma questão repetida em nenhum conjunto.

**Correções que saíram da F0 (PR "Exact question format and shuffled options"):** o painel agora exige exatamente N questões com N alternativas (vai como JSON schema, então o LM Studio obriga), e embaralha as alternativas, então nenhum modelo consegue concentrar a certa numa letra.

**Recomendação:** modelo padrão `google/gemma-4-26b-a4b-qat` (melhor qualidade, menos de 3 minutos). Se 3 minutos por conjunto parecer lento, o `google/gemma-4-e4b` é a opção rápida (~47 s). **Decisão: do dono** (Gerenciar → Configurações → Modelo padrão).
