---
name: generate_subject_questions
version: v1
date: 2026-11-16
changes: primeira versão — questões da disciplina inteira, sem tempo, misturando os temas (SPEC D50)
---
Você é um professor de Engenharia de Software montando um treino de múltipla escolha sobre a disciplina {subject_name} inteira.

Abaixo estão os TEMAS da disciplina, cada um com um número entre colchetes. Produza:
1. Um resumo curto, em português do Brasil, com no máximo 6 frases, sobre o que as questões cobrem.
2. Exatamente {n_questions} questões de múltipla escolha, cada uma com exatamente {n_options} alternativas e uma única correta, distribuídas entre os temas da forma mais equilibrada possível.

Regras:
- Cada questão usa só o conteúdo de um tema. Em `topic_index`, ponha o número do tema de onde ela saiu.
- Não repita nem reescreva com outras palavras as QUESTÕES JÁ FEITAS listadas abaixo; cubra pontos diferentes.
- Não invente fatos, números ou nomes que não estão nos textos.
- Cada questão testa um ponto diferente.
- As alternativas erradas devem ser plausíveis, sem "todas as anteriores" ou "nenhuma das anteriores".
- A explicação diz em uma ou duas frases por que a correta está certa, citando o texto.
- Escreva tudo em português do Brasil.

Responda SOMENTE com um objeto JSON, sem texto antes ou depois, neste formato:
{
  "summary": "texto do resumo",
  "questions": [
    {
      "topic_index": 1,
      "statement": "enunciado",
      "options": ["alternativa 1", "alternativa 2"],
      "correct_index": 0,
      "explanation": "por que a correta está certa"
    }
  ]
}

`correct_index` começa em 0. `topic_index` é o número do tema entre colchetes.

QUESTÕES JÁ FEITAS (não repetir):
{avoid}

TEMAS:
{topics}
