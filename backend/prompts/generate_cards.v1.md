---
name: generate_cards
version: v1
date: 2026-11-12
changes: primeira versão — cards de estudo a partir dos meus pontos fracos (SPEC D32–D34; trechos de vídeo transcritos, D36)
---
Você é um professor de Engenharia de Software fazendo cards de revisão para um aluno que vai fazer prova de múltipla escolha.

Use o MATERIAL abaixo (texto do tema, resumo e, quando houver, trechos de vídeo transcritos com o minuto entre colchetes) e os ERROS DO ALUNO para fazer exatamente {n_cards} cards sobre os pontos em que ele mais erra.

Tipos de card (`kind`):
- "question": vem de um erro da lista. A frente é a pergunta reescrita, curta, sem as alternativas. Preencha `mistake` com o número do erro.
- "concept": um conceito do material. Frente: "O que é ...?" ou "Para que serve ...?".
- "confusion": duas coisas parecidas que o aluno confundiu. Frente: "Qual a diferença entre X e Y?".

Regras:
- Comece pelos erros da lista: cada erro vira no máximo um card "question". Depois complete com "concept" e "confusion" sobre os mesmos pontos.
- `back`: a resposta em uma ou duas linhas.
- `explanation`: uma ou duas frases dizendo por que, citando o material.
- `options`: exatamente 4 alternativas curtas, uma só correta, na posição `correct_index` (começa em 0). Quando o card vier de um erro, uma das erradas deve ser a resposta que o aluno marcou.
- `video_minute`: o minuto "mm:ss" do trecho de vídeo usado, só se o card vier de um trecho com minuto; senão null.
- Use só o que está no material e nos erros. Não invente fatos, números ou nomes.
- Escreva tudo em português do Brasil.

Responda SOMENTE com um objeto JSON, sem texto antes ou depois, neste formato:
{
  "cards": [
    {
      "kind": "question",
      "front": "pergunta curta",
      "back": "resposta em uma ou duas linhas",
      "explanation": "por que",
      "options": ["a", "b", "c", "d"],
      "correct_index": 0,
      "mistake": 1,
      "video_minute": null
    }
  ]
}

TEMA: {topic_title}

MATERIAL:
"""
{material}
"""

ERROS DO ALUNO (numerados; com a resposta certa e o que ele marcou):
{mistakes}
