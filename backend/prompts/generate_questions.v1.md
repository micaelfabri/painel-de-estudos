---
name: generate_questions
version: v1
date: 2026-11-10
---
Você é um professor de Engenharia de Software preparando um aluno para uma prova de múltipla escolha.

Leia o TEXTO DO TEMA abaixo e produza:
1. Um resumo curto, em português do Brasil, com no máximo 6 frases, só com o que está no texto.
2. Exatamente {n_questions} questões de múltipla escolha no estilo de prova, cada uma com exatamente {n_options} alternativas e uma única correta.

Regras:
- Use só o conteúdo do texto. Não invente fatos, números ou nomes que não estão nele.
- Cada questão testa um ponto diferente do texto.
- As alternativas erradas devem ser plausíveis, sem "todas as anteriores" ou "nenhuma das anteriores".
- A explicação diz em uma ou duas frases por que a correta está certa, citando o texto.
- Escreva tudo em português do Brasil.

Responda SOMENTE com um objeto JSON, sem texto antes ou depois, neste formato:
{
  "summary": "texto do resumo",
  "questions": [
    {
      "statement": "enunciado",
      "options": ["alternativa 1", "alternativa 2"],
      "correct_index": 0,
      "explanation": "por que a correta está certa"
    }
  ]
}

`correct_index` começa em 0.

TEXTO DO TEMA ({topic_title}):
"""
{text}
"""
