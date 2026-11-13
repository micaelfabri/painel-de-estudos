---
name: read_print_card
version: v1
date: 2026-11-12
changes: primeira versão — transcrever a questão de um print para virar card (SPEC D36, autorizado em 12/11/2026, só modelo local)
---
Você vai ver UM print de tela de uma questão de múltipla escolha que um aluno respondeu numa plataforma de estudos (atividade, laboratório, simulado ou prova).

Transcreva o que o print mostra:
- `result`: "correct" se o print mostra que a resposta marcada está CERTA; "wrong" se mostra que está ERRADA; "unknown" se não dá para saber.
- `statement`: o enunciado da questão, como está no print (pode resumir se for muito longo, sem mudar o sentido). Se não der para ler, "".
- `options`: as alternativas, na ordem do print, sem a letra. Se não der para ler, [].
- `correct_index`: a posição (começando em 0) da alternativa que o print mostra como correta. Se o print não mostrar a correta, null.
- `chosen_index`: a posição da alternativa que o aluno marcou, se aparecer; senão null.
- `explanation`: se o print trouxer um comentário ou gabarito explicando, resuma em uma ou duas frases; senão "".

Não invente: copie só o que está legível no print.

Responda SOMENTE com um objeto JSON, sem texto antes ou depois, neste formato:
{
  "result": "wrong",
  "statement": "enunciado",
  "options": ["alternativa 1", "alternativa 2", "alternativa 3", "alternativa 4"],
  "correct_index": 2,
  "chosen_index": 0,
  "explanation": ""
}
