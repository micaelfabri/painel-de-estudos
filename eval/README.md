# F0 — teste de modelos / model test

Bilingual file (DIRETRIZ_BILINGUE_v1): English first, Portuguese after. If they differ, the Portuguese prevails.

## ENGLISH

Compares 2–3 local models on 3 real topics with the **same prompt and validator as the app** (SPEC §7). The cloud session has no GPU, so this runs on your PC.

It uses **the same client as the app** (same formats, retry and cut-off detection), so what passes here passes in the panel.

1. Paste the text of 3 real topics into `eval/topics/` as `.txt` files (e.g. `seguro-tema3-modulo2.txt`). Only the content text, one module per file (under 30,000 characters).
2. LM Studio: Model Server running with "Serve on Local Network" on; for each model, Context Length **16384** and thinking **off** (Library → gear icon).
3. In PowerShell, in the project folder (runs inside Docker, no Python needed on Windows):
   ```powershell
   docker compose build
   docker compose run --rm -v "${PWD}\eval:/app/eval" app python /app/eval/run_eval.py --base-url http://host.docker.internal:1234/v1 --options 5 --models qwen/qwen3.5-9b google/gemma-4-12b-it-qat google/gemma-4-e4b-it
   ```
   Big models on 8 GB can take several minutes per topic: the default wait is 900 s (`--timeout` to change).
   Model names: copy them exactly from Gerenciar → Configurações → "Modelo padrão" (same list). `--options 5` = alternatives per question; confirm on a real exam.
4. Open the `eval/RESULTS_<date>.md` it creates. The numbers (valid JSON, attempts, time, tokens) are filled in. You fill in the 1–5 ratings and pick the default model.
5. Set that model as the default in Gerenciar → Configurações.

`eval/topics/*.txt` and `eval/results/` are in `.gitignore` (course text stays on your PC). RESULTS files are ignored too; to keep the chosen one: `git add -f eval/RESULTS_<date>.md`.

## PORTUGUÊS

Compara 2–3 modelos locais em 3 temas reais com **o mesmo prompt e o mesmo validador do app** (SPEC §7). A sessão na nuvem não tem GPU, então isso roda no seu PC.

Usa **o mesmo cliente do app** (mesmos formatos, nova tentativa e detecção de resposta cortada), então o que passa aqui passa no painel.

1. Cole o texto de 3 temas reais em `eval/topics/` como arquivos `.txt` (ex.: `seguro-tema3-modulo2.txt`). Só o texto do conteúdo, um módulo por arquivo (menos de 30.000 caracteres).
2. LM Studio: Model Server ligado com "Serve on Local Network"; em cada modelo, Context Length **16384** e raciocínio (thinking) **desligado** (Library → engrenagem).
3. No PowerShell, na pasta do projeto (roda dentro do Docker, sem precisar de Python no Windows):
   ```powershell
   docker compose build
   docker compose run --rm -v "${PWD}\eval:/app/eval" app python /app/eval/run_eval.py --base-url http://host.docker.internal:1234/v1 --options 5 --models qwen/qwen3.5-9b google/gemma-4-12b-it-qat google/gemma-4-e4b-it
   ```
   Modelos grandes em 8 GB podem levar vários minutos por tema: a espera padrão é 900 s (`--timeout` para mudar).
   Nomes dos modelos: copie exatamente de Gerenciar → Configurações → "Modelo padrão" (a mesma lista). `--options 5` = alternativas por questão; confira numa prova real.
4. Abra o `eval/RESULTS_<data>.md` que ele cria. Os números (JSON válido, tentativas, tempo, tokens) já vêm preenchidos. Você preenche as notas de 1 a 5 e escolhe o modelo padrão.
5. Defina esse modelo como padrão em Gerenciar → Configurações.

`eval/topics/*.txt` e `eval/results/` estão no `.gitignore` (o texto das matérias fica no seu PC). Os RESULTS também ficam ignorados; para guardar o escolhido: `git add -f eval/RESULTS_<data>.md`.
