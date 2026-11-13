---
name: read_print
version: v1
date: 2026-11-12
changes: primeira versão — ler um print de questão (atividade, laboratório, prova) e dizer se a resposta marcada está certa ou errada (SPEC D17)
---
Você vai ver UM print de tela de uma questão de múltipla escolha que um aluno respondeu numa plataforma de estudos (atividade, laboratório, simulado ou prova).

Diga o que o print mostra:
- `question_number`: o número da questão, se aparecer no print (ex.: "Questão 3", "3/10"). Se não aparecer, null.
- `result`: "correct" se o print mostra que a resposta marcada está CERTA (ex.: verde, "Correto", "Resposta correta", ícone de certo); "wrong" se mostra que está ERRADA (ex.: vermelho, "Incorreto", "Resposta errada", ícone de X); "unknown" se não dá para saber.
- `note`: uma frase curta dizendo o que você viu que levou à resposta.

Não invente: se o print não mostrar claramente se está certo ou errado, use "unknown".

Responda SOMENTE com um objeto JSON, sem texto antes ou depois, neste formato:
{
  "question_number": 3,
  "result": "correct",
  "note": "faixa verde com o texto Resposta correta"
}
