import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Guia de uso dentro do app (opção C: instalação no docs/GUIA.md e no PDF; uso aqui).
// Mesmo conteúdo da seção "Usando" e "Problemas" do docs/GUIA.md: ao mudar um, mude o outro.
const SECTIONS: { title: string; items: string[] }[] = [
  {
    title: "Começar o dia",
    items: [
      "Abra o Docker Desktop e o LM Studio (Developer → Local Server → Status: Running).",
      "No PowerShell, na pasta do projeto: docker compose up. Abra http://localhost:8000.",
      "No painel do agente, clique em \"Montar o dia\": entram os retestes vencidos e o próximo passo de estudo.",
    ],
  },
  {
    title: "Estudar um tema",
    items: [
      "No cronômetro, escolha a disciplina e clique em Iniciar. Cada pausa salva o trecho estudado.",
      "Meta de 1h30 por tema; o alarme toca em 2h. Os dois valores mudam em Configurações.",
      "Ao terminar, marque o tema como \"Concluído no portal\" em Gerenciar → Disciplinas e temas.",
    ],
  },
  {
    title: "Gerar e responder questões",
    items: [
      "Clique em \"Gerar questões\", escolha disciplina e tema e cole o texto de um módulo por vez (até 30.000 caracteres).",
      "Escolha o número de alternativas e clique em \"Gerar resumo e questões\". A primeira vez demora mais: o LM Studio carrega o modelo.",
      "Responda sem consultar. No fim aparece o % de acerto e os pontos para rever no vídeo.",
      "Questão mal feita? \"Marcar questão ruim\" tira ela da nota.",
    ],
  },
  {
    title: "Retestes e aprendizado",
    items: [
      "Depois do primeiro conjunto de um tema, o painel agenda retestes em 1, 7 e 21 dias.",
      "O reteste de 7 dias decide: 70% ou mais = aprendido; abaixo = revisar, com novo reteste em 3 dias.",
      "Retestes vencidos aparecem primeiro em \"Próxima ação sugerida\" e no \"Montar o dia\".",
      "\"Revisar erros\" mostra cada resposta errada com a certa e a explicação.",
    ],
  },
  {
    title: "Cadastros (Gerenciar)",
    items: [
      "Disciplinas e temas: disciplina, regra de avaliação, progresso do portal e lista de temas.",
      "Provas e prazos: data, hora e local de cada prova; aparecem nos cards e na faixa de 14 dias.",
      "Semestres e curso: semestre atual e progresso do curso.",
      "Atividades complementares: horas de ACC lançadas e planejadas contra o total exigido.",
      "Configurações: metas, endereço do modelo local, modelo padrão e registro de uso do modelo.",
    ],
  },
  {
    title: "Quando algo dá errado",
    items: [
      "0.0.0.0:8000 não abre: use http://localhost:8000.",
      "\"Modelo local fora do ar\": ligue o servidor do LM Studio com \"Serve on Local Network\" e confira o endereço em Configurações (http://host.docker.internal:1234/v1).",
      "\"A resposta do modelo foi cortada\": no LM Studio, Context Length 16384 e raciocínio (thinking) desligado; ou cole um trecho menor.",
      "Muito lento: use um modelo menor (gemma-4-E4B) e feche apps pesados.",
      "Passo a passo completo, com prints: docs/GUIA.md e docs/guia/GUIA.pdf no projeto.",
    ],
  },
];

/** Gerenciar › Como usar */
export function HelpPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Como usar</h1>
        <p className="text-sm text-muted-foreground">O básico de cada tela. Instalação e credenciais: docs/GUIA.md.</p>
      </header>
      <div className="grid gap-4 md:grid-cols-2">
        {SECTIONS.map((s) => (
          <Card key={s.title}>
            <CardHeader>
              <CardTitle>{s.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="list-decimal space-y-2 pl-5 text-sm">
                {s.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ol>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
