import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Guia de uso dentro do app (opção C: instalação no docs/GUIA.md e no PDF; uso aqui).
// Mesmo conteúdo da seção "Usando" e "Problemas" do docs/GUIA.md: ao mudar um, mude o outro.
const SECTIONS: { title: string; items: string[] }[] = [
  {
    title: "Começar o dia",
    items: [
      "Abra o Docker Desktop e o LM Studio (Developer → Local Server → Status: Running).",
      "No PowerShell, na pasta do projeto: docker compose up. Abra http://localhost:8000.",
      'No painel do agente, clique em "Montar o dia": entram os retestes vencidos e o próximo passo de estudo. Tarefas não feitas de dias anteriores: "Trazer para hoje".',
    ],
  },
  {
    title: "Estudar um tema",
    items: [
      "No cronômetro, escolha a disciplina e clique em Iniciar. Cada pausa salva o trecho estudado.",
      "Finalizar fecha a sessão: tempo estudado, tempo total (com as pausas) e número de pausas ficam salvos.",
      "Meta de 1h30 por tema; o alarme toca em 2h. Os dois valores mudam em Configurações.",
      'Ao terminar, marque o tema como "Concluído no portal" em Gerenciar → Disciplinas e temas.',
    ],
  },
  {
    title: "Gerar e responder questões",
    items: [
      'Clique em "Gerar questões", escolha disciplina e tema e cole o texto de um módulo por vez (até 30.000 caracteres).',
      'Escolha o número de alternativas e clique em "Gerar resumo e questões". A primeira vez demora mais: o LM Studio carrega o modelo.',
      "Responda sem consultar. No fim aparece o % de acerto e os pontos para rever no vídeo.",
      'Questão mal feita? "Marcar questão ruim" tira ela da nota.',
      'A conversa com o agente fica salva; "Limpar conversa" apaga só as mensagens.',
    ],
  },
  {
    title: "Retestes e aprendizado",
    items: [
      "Depois do primeiro conjunto de um tema, o painel agenda retestes em 1, 7 e 21 dias.",
      "O reteste de 7 dias decide: 70% ou mais = aprendido; abaixo = revisar, com novo reteste em 3 dias.",
      "Se o reteste de 21 dias ficar abaixo de 70%, o tema volta para revisar. Refazer, testes de foco e simulados não mudam o status.",
      'Retestes vencidos aparecem primeiro em "Próxima ação sugerida" e no "Montar o dia".',
    ],
  },
  {
    title: "Ciclo dos erros",
    items: [
      'Todo erro começa como Não revisado. Em "Revisar erros", leia a certa e a explicação e clique em "Já revisei".',
      '"Refazer erros não corrigidos" monta um conjunto com até 10 erros, na hora, sem o modelo.',
      "No refazer, acertou = Corrigido; errou = Revisar de novo. Refazer nunca cria erro novo.",
      'No Histórico, cada tema mostra os erros por status e tem o botão "Refazer erros".',
    ],
  },
  {
    title: "Cards",
    items: [
      'Estudo → Cards → "Gerar cards dos meus pontos fracos": 10 cards dos erros não corrigidos e dos temas abaixo de 70%.',
      '"De prints ou de vídeo": cards das questões erradas nos prints ou de uma transcrição de vídeo (.vtt, .srt, .txt ou colada).',
      "Responder (4 alternativas) ou Virar (Sabia/Não sabia). Card de um erro: errou = revisar de novo; acertou = corrigido.",
      'Cada card volta em 1, 7, 21 e 60 dias; "Não sabia" volta para 1 dia. Rodada rápida: 10 cards com tempo e sequência.',
      'O card do dia fica no Painel. "Notion" acrescenta os cards na página do tema, sem apagar nada.',
    ],
  },
  {
    title: "Provas, notas e desempenho",
    items: [
      "Estudo → Provas e prazos: tudo numa lista. Marcar a caixa pede confirmação.",
      "Resultado: o painel lê os prints (Notion ou pasta de materiais) e propõe a nota; você confirma. Simulado vale até 1,0 ponto.",
      "O card de cada disciplina mostra a nota prevista e quanto falta na AV/AVS para passar, pela regra da disciplina.",
      "Desempenho: filtre por período e disciplina; clique numa barra para ver o dia (com as tarefas do checklist daquele dia) e num ponto para abrir o teste.",
    ],
  },
  {
    title: "Cursos e certificados",
    items: [
      "Cursos fora da faculdade (livres, certificações, idiomas, bootcamps) ficam no grupo próprio do menu; o Painel continua só com a faculdade.",
      'Meus cursos: "Novo curso" com plataforma, tipo, carga horária e número de módulos. Abas por situação: Fazendo, Quero fazer, Pausado, Concluído.',
      'Na página do curso: marque as aulas vistas, cole o texto da aula para gerar questões e cards, e use o cronômetro (os módulos aparecem como "Curso: …").',
      'As horas dos cursos têm meta própria (5h por semana, em Configurações) e não entram na meta da faculdade. Para os cursos entrarem em "Montar o dia", ligue em Configurações.',
      "Histórico, Cards e Desempenho do grupo mostram só os cursos. A prova de certificação aparece só aqui, não em Provas e prazos.",
      'Curso que conta como AAC: ao concluir, "Lançar como AAC" cria a atividade em Atividades complementares, uma vez só.',
    ],
  },
  {
    title: "Cadastros (Gerenciar)",
    items: [
      "Disciplinas e temas: disciplina, regra de avaliação, progresso do portal e lista de temas.",
      "Provas e prazos: data, hora e local de cada prova; aparecem nos cards e na faixa de 14 dias.",
      "Semestres e curso: semestre atual e progresso do curso.",
      "Atividades complementares: horas de ACC lançadas e planejadas contra o total exigido; para tirar uma, Editar › Excluir atividade.",
      "Configurações: metas (faculdade e cursos), modelo local, teste de leitura de imagem, links do rodapé, integrações e registro de uso.",
      '"Mandar provas para a agenda" lista as provas antes; só vão as marcadas.',
    ],
  },
  {
    title: "Quando algo dá errado",
    items: [
      "0.0.0.0:8000 não abre: use http://localhost:8000.",
      '"Modelo local fora do ar": ligue o servidor do LM Studio com "Serve on Local Network" e confira o endereço em Configurações (http://host.docker.internal:1234/v1).',
      '"A resposta do modelo foi cortada": no LM Studio, Context Length 16384 e raciocínio (thinking) desligado; ou cole um trecho menor.',
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
