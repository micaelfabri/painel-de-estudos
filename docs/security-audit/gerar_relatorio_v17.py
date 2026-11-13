"""Gera docs/security-audit/relatorio-auditoria-seguranca-v1.7.pdf (pt-BR): auditoria da atualização v1.7.

Uso (ambiente isolado, nada global):
    python -m venv .venv-audit && .venv-audit/bin/pip install reportlab matplotlib
    .venv-audit/bin/python docs/security-audit/gerar_relatorio_v17.py

Os achados ficam nas listas abaixo; para regerar depois de uma correção, mude o status e rode de novo.
"""

from datetime import date
from io import BytesIO
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle,
)

OUT = Path(__file__).resolve().parent / "relatorio-auditoria-seguranca-v1.7.pdf"
PROJETO = "Painel de Estudos"
TITULO = f"Relatório de Auditoria de Segurança — {PROJETO} v1.7"
DATA = date(2026, 11, 12)

COR = {"crítica": "#B91C1C", "alta": "#EA580C", "média": "#D97706", "baixa": "#2563EB",
       "informativa": "#64748B", "ponto forte": "#059669"}
ORDEM = ["crítica", "alta", "média", "baixa", "informativa"]

# --- Achados verificados ------------------------------------------------------
# status: "corrigido" (nesta versão), "aberto" (vira issue), "aceito" (risco aceito por decisão do SPEC)
ACHADOS = [
    {
        "id": 1, "cat": "Dados pessoais (cópia pública)", "sev": "média", "status": "corrigido",
        "arq": "backend/tests, frontend/src, settings_store.py, .env.example, AppFooter.tsx, docs/propostas, SPEC.md, CLAUDE.md",
        "titulo": "Dados reais do dono na atualização exportada da versão privada",
        "desc": "As versões v1.3 a v1.7 trouxeram de volta dados do dono: nomes reais de disciplinas e do polo nos "
                "testes, ids de regra com o nome da faculdade, nome do dono no rodapé e em comentários, links do "
                "GitHub e do LinkedIn do dono como padrão nas Configurações, o caminho real da pasta de materiais no "
                ".env.example e nas decisões do SPEC, e duas imagens de proposta com a agenda e as disciplinas reais.",
        "trecho": "\"github_url\": (str | None, \"https://github.com/<dono>\", ...)\n# PAINEL_MATERIALS_HOST=D:/<caminho real>",
        "fix": "Mesmo mapeamento da v1 (disciplinas, polo e regras fictícios); links do rodapé vazios por padrão; "
               "rodapé \"© <ano> Painel de Estudos\"; caminho de exemplo no .env.example; SPEC e CLAUDE.md sem nome, "
               "caminho ou datas da faculdade; docs/propostas fora da cópia pública; prints e guia refeitos com "
               "atividade fictícia. Conferido por grep, texto do PDF e OCR dos 21 prints (ampliados 2×, com controle: "
               "o título foi lido em 21 de 21).",
        "impacto": "Exposição de dados pessoais e da rotina do dono.",
        "aceite": ["grep por nome, instituição, polo, caminhos, e-mail e links pessoais sem resultados",
                   "OCR dos prints e texto do PDF sem dados reais"],
    },
    {
        "id": 2, "cat": "Dependências", "sev": "média", "status": "corrigido",
        "arq": "backend/requirements.txt",
        "titulo": "Pillow 12.1.1 com vulnerabilidades conhecidas",
        "desc": "A v1.3 passou a abrir imagens (prints das respostas, de páginas do Notion ou da pasta de materiais) "
                "com o Pillow 12.1.1, que o pip-audit apontou com 75 vulnerabilidades conhecidas. Um arquivo de "
                "imagem preparado poderia explorar o decodificador dentro do container.",
        "trecho": "pillow==12.1.1",
        "fix": "Pillow 13.0.0 (v1.7). pip-audit -r backend/requirements.txt: nenhuma vulnerabilidade; npm audit: 0.",
        "impacto": "Execução ou travamento ao abrir uma imagem maliciosa.",
        "aceite": ["pip-audit sem vulnerabilidades", "testes de leitura de prints passando"],
    },
    {
        "id": 3, "cat": "IA local / entrada não confiável", "sev": "informativa", "status": "aceito",
        "arq": "backend/app/cards.py, backend/app/integrations/prints.py, backend/prompts/read_print*.md",
        "titulo": "Instruções escondidas em prints ou transcrições (prompt injection)",
        "desc": "Prints e transcrições vão como material para o modelo local. Um texto ali dentro pode tentar mudar o "
                "comportamento do modelo. O modelo não tem ferramentas nem acesso à rede ou a arquivos; a saída é "
                "validada por schema Pydantic e mostrada como texto. O pior caso é um card ou uma nota proposta "
                "errada; a nota só é salva depois que o dono confirma.",
        "trecho": "material.append(f\"TRECHOS DE VÍDEO ({transcript_label}):\\n{transcript[:MAX_TRANSCRIPT]}\")",
        "fix": "Nenhuma ação agora (SPEC D17, D36).",
        "impacto": "—", "aceite": [],
    },
    {
        "id": 4, "cat": "Privacidade / IA local", "sev": "informativa", "status": "aceito",
        "arq": "backend/app/agent/router.py, backend/app/study.py, settings_store.py",
        "titulo": "Prints e resumo dos números de estudo vão para o modelo local",
        "desc": "Exceção decidida no SPEC (D17/D18, D25, D36): prints das respostas e um resumo curto de horas, notas e "
                "temas vão só para o modelo local (LM Studio ou Ollama no próprio PC). O resumo dá para desligar em "
                "Configurações. Nada vai para IA na nuvem.",
        "trecho": "\"agent_reads_metrics\": (bool, True, ...)",
        "fix": "Nenhuma ação agora.",
        "impacto": "—", "aceite": [],
    },
    {
        "id": 5, "cat": "Isolamento / autenticação", "sev": "informativa", "status": "aceito",
        "arq": "docker-compose.yml",
        "titulo": "Sem login, por decisão do SPEC (D1)",
        "desc": "Igual à v1: a barreira é a porta presa ao loopback + validação de Host + bloqueio de escrita vinda "
                "de outro site, conferido também nas rotas novas.",
        "trecho": '- "127.0.0.1:8000:8000"',
        "fix": "Nenhuma ação agora.",
        "impacto": "—", "aceite": [],
    },
]

PONTOS_FORTES = [
    ("Porta só no loopback", "docker-compose.yml publica 127.0.0.1:8000; nada exposto na rede."),
    ("Host validado (DNS rebinding)", "Host: evil.com → 400 contra o app rodando."),
    ("Escrita só da própria página, rotas novas incluídas", "POST /api/cards/round com Origin externo → 403; "
     "POST /api/cards/{id}/review com Sec-Fetch-Site cross-site → 403; text/plain → 422."),
    ("Pasta de materiais", "Montada só para leitura; /api/prints/folder?path=../../etc → 400 \"Caminho fora da pasta "
     "de materiais\"; testes de travessia para prints e transcrições."),
    ("Limites de entrada", "Transcrição: 30 mil caracteres colados ou arquivo até 2 MB; imagens: 15 MB, 40 por "
     "análise, PDF até 30 páginas, reduzidas a 1280 px antes do modelo."),
    ("Links dinâmicos controlados", "Link do Notion no card sempre começa com https://www.notion.so/; links do "
     "rodapé só aceitam https:// (no servidor e na tela), com rel=\"noopener noreferrer\"."),
    ("Cabeçalhos de segurança", "CSP só 'self', frame-ancestors 'none', X-Frame-Options DENY, nosniff, no-referrer."),
    ("Sem SQL cru com f-string", "Acesso ao banco pelo ORM; migrações usam parâmetros nomeados."),
    ("Sem sinks de XSS", "Nenhum dangerouslySetInnerHTML, innerHTML, eval, new Function ou window.open; saída do "
     "modelo renderizada como texto."),
    ("Sem segredos", "Busca por padrões (ntn_, secret_, sk-, ghp_, github_pat_, AIza, GOCSPX-, chave privada, "
     "refresh_token): nenhum resultado no código, docs ou compose."),
    ("Arquivos estáticos seguros", "/..%2f..%2fetc%2fpasswd devolve o index.html."),
    ("Dependências limpas", "pip-audit: nenhuma vulnerabilidade (depois do #2); npm audit: 0."),
    ("CI", "GitHub Actions em todo pull request: ruff + pytest (103 testes) e tsc + vitest (14) + build."),
]

NAO_SE_APLICA = [
    ("1. Banco sem tranca (tenant)", "App de um usuário só, sem contas nem tenants (SPEC D1)."),
    ("2. Permissão no navegador", "Não existem papéis no frontend nem no backend."),
    ("3. IDOR", "As rotas novas por ID (cards, histórico, provas e prazos, cronômetro) foram percorridas: todo "
     "objeto pertence ao único usuário."),
    ("4. Chaves expostas", "Aplicável e verificado: nenhum achado (ver pontos fortes)."),
    ("5. XSS", "Aplicável e verificado: nenhum achado (ver pontos fortes)."),
]

RECOMENDACOES = [
    ("P2", "No Docker Desktop do Windows, depois do docker compose up --build, conferir que o painel sobe e mostra "
     "a data de hoje depois das 21:00 (fuso America/Sao_Paulo da v1.7)."),
    ("P3", "Ativar Dependabot ou rodar npm audit e pip-audit a cada atualização."),
    ("P3", "A cada nova versão pública: repetir grep + OCR dos prints e deixar fora as imagens de proposta."),
]

CHECKLIST = [
    ("Rodei o prompt e li o PDF inteiro", "Para o dono fazer: ler este relatório."),
    ("Todo endpoint com ID valida o dono", "Não se aplica: um usuário só."),
    ("Toda listagem filtra por usuário/tenant", "Não se aplica: sem tenants."),
    ("Permissão escondida no front é conferida no servidor", "Não se aplica: sem papéis."),
    ("Nenhum segredo no código, bundle, compose ou CI", "OK: verificado."),
    ("Busca no histórico git e revogação", "OK: o histórico público só tem a v1 e esta atualização; nada a revogar."),
    ("Input validado antes de virar HTML", "OK: React escapa; sem sinks de HTML; links dinâmicos só https."),
    ("Supabase: RLS e service_role", "Não se aplica: SQLite local."),
    ("Achados viraram issue ou advisory", "Achados acionáveis corrigidos; nenhuma issue em aberto."),
]


# --- Estilos -----------------------------------------------------------------
# Fonte DejaVu que vem junto do matplotlib: tem ✔, →, ≤ e acentos em qualquer SO
from reportlab.lib.fonts import addMapping  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402

_TTF = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
for nome, arq in [("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"), ("DV-I", "DejaVuSans-Oblique.ttf"),
                  ("DV-BI", "DejaVuSans-BoldOblique.ttf"), ("DVM", "DejaVuSansMono.ttf")]:
    pdfmetrics.registerFont(TTFont(nome, str(_TTF / arq)))
addMapping("DV", 0, 0, "DV")
addMapping("DV", 1, 0, "DV-B")
addMapping("DV", 0, 1, "DV-I")
addMapping("DV", 1, 1, "DV-BI")

ss = getSampleStyleSheet()
for _st in ss.byName.values():
    _st.fontName = "DVM" if "Code" in _st.name else ("DV-B" if "Heading" in _st.name or _st.name == "Title" else "DV")
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=18, spaceAfter=10, textColor=colors.HexColor("#111827"))
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=6)
P = ParagraphStyle("P", parent=ss["BodyText"], fontSize=9.5, leading=13, alignment=TA_LEFT)
SMALL = ParagraphStyle("S", parent=P, fontSize=8.5, leading=11)
CODE = ParagraphStyle("C", parent=ss["Code"], fontSize=7.5, leading=9.5, backColor=colors.HexColor("#F3F4F6"),
                      borderPadding=4, leftIndent=4, rightIndent=4)


def chip(sev: str) -> Paragraph:
    return Paragraph(f'<font color="white"><b>&nbsp;{sev.upper()}&nbsp;</b></font>',
                     ParagraphStyle("chip", parent=SMALL, fontSize=7.5, backColor=colors.HexColor(COR[sev]),
                                    alignment=1, borderPadding=2))


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fig_png(fig) -> BytesIO:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def graficos():
    contagem = {s: sum(1 for a in ACHADOS if a["sev"] == s) for s in ORDEM}
    contagem["ponto forte"] = len(PONTOS_FORTES)
    labels = [k for k, v in contagem.items() if v]
    vals = [contagem[k] for k in labels]
    fig, ax = plt.subplots(figsize=(4, 3.2))
    ax.pie(vals, labels=[f"{k} ({v})" for k, v in zip(labels, vals)], colors=[COR[k] for k in labels],
           startangle=90, wedgeprops={"width": 0.38, "edgecolor": "white"}, textprops={"fontsize": 8})
    ax.set_title("Achados por severidade\n(+ pontos fortes)", fontsize=9)
    rosca = fig_png(fig)

    cats = list(dict.fromkeys(a["cat"] for a in ACHADOS))
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    base = [0] * len(cats)
    for s in ORDEM:
        vals = [sum(1 for a in ACHADOS if a["cat"] == c and a["sev"] == s) for c in cats]
        if any(vals):
            ax.barh([__import__("textwrap").fill(c, 18) for c in cats], vals, left=base, color=COR[s], label=s)
            base = [b + v for b, v in zip(base, vals)]
    ax.invert_yaxis()
    ax.set_xlabel("achados", fontsize=8)
    ax.tick_params(labelsize=7.5)
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Achados por categoria", fontsize=9)
    barras = fig_png(fig)
    return rosca, barras


def cabecalho(canvas, doc):
    canvas.saveState()
    canvas.setFont("DV", 8)
    canvas.setFillColor(colors.HexColor("#6B7280"))
    canvas.drawString(2 * cm, A4[1] - 1.3 * cm, TITULO)
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.drawString(2 * cm, 1.2 * cm, f"{PROJETO} · {DATA:%d/%m/%Y}")
    canvas.restoreState()


def issue_md(n: int, a: dict) -> str:
    return f"""--- ISSUE {n} ---
## [Segurança] {a['titulo']}

**Labels:** security, severity:{a['sev']}

### Problema
{a['desc']}

### Evidência
`{a['arq']}`

```
{a['trecho']}
```

### Impacto
{a['impacto']}

### Sugestão de correção
{a['fix']}

### Critérios de aceite
{chr(10).join('- [ ] ' + c for c in a['aceite'])}
--- FIM ISSUE {n} ---"""


def montar():
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm, title=TITULO, author="Auditoria automatizada")
    W = A4[0] - 4 * cm
    s = []

    # a) Capa
    s += [Spacer(1, 3 * cm), Paragraph(TITULO, ParagraphStyle("T", parent=H1, fontSize=22, leading=27)),
          Spacer(1, 0.4 * cm), Paragraph(f"Data: {DATA:%d/%m/%Y}", P), Spacer(1, 0.8 * cm),
          Paragraph("<b>Escopo</b>", H2),
          Paragraph("Atualização da cópia pública painel-de-estudos da v1 para a v1.7 (dados fictícios), antes do push: "
                    "backend FastAPI + SQLAlchemy + SQLite, frontend React + Vite + TypeScript, Dockerfile, "
                    "docker-compose, bundle compilado, prints e guia em PDF. Foco no que mudou desde a v1: histórico, "
                    "cronômetro, desempenho, prints e pasta de materiais, cards, transcrições, rodapé e CI.", P),
          Paragraph("<b>Stack detectada e como cada categoria foi mapeada</b>", H2),
          Paragraph("App local de um usuário, sem autenticação (SPEC D1), porta presa a 127.0.0.1. "
                    "(1) Isolamento: não há tenant; foi auditado o isolamento de rede (loopback, Host, CORS, CSRF). "
                    "(2) Permissão no navegador e (3) IDOR: não há papéis nem donos; todos os routers foram "
                    "percorridos para confirmar. (4) Chaves: código, compose, .env.example, histórico git e bundle. "
                    "(5) XSS: sinks no React e renderização da saída do modelo. Além das cinco, foram auditados "
                    "cabeçalhos HTTP, dependências (pip-audit, npm audit) e o container.", P),
          Paragraph("<b>Método</b>", H2),
          Paragraph("Leitura de código + testes contra o app rodando (curl): Host forjado, POST text/plain, "
                    "POST com Origin e Sec-Fetch-Site de outro site nas rotas novas, travessia de caminho na pasta "
                    "de materiais e nos arquivos estáticos; os testes automáticos de travessia e de escrita de outro "
                    "site; grep de segredos e dados pessoais; OCR dos prints (ampliados, com controle) e texto do "
                    "PDF; pip-audit e npm audit.", P),
          PageBreak()]

    # b) Resumo executivo
    abertos = [a for a in ACHADOS if a["status"] == "aberto"]
    s += [Paragraph("Resumo executivo", H1)]
    linhas = [["Severidade", "Total", "Corrigidos", "Abertos", "Aceitos"]]
    for sev in ORDEM:
        xs = [a for a in ACHADOS if a["sev"] == sev]
        linhas.append([chip(sev), len(xs), sum(a["status"] == "corrigido" for a in xs),
                       sum(a["status"] == "aberto" for a in xs), sum(a["status"] == "aceito" for a in xs)])
    linhas.append([chip("ponto forte"), len(PONTOS_FORTES), "—", "—", "—"])
    t = Table(linhas, colWidths=[3.6 * cm] + [2.6 * cm] * 4)
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "DV-B", 9), ("FONTSIZE", (0, 1), (-1, -1), 9),
                           ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.grey),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")])]))
    s += [t, Spacer(1, 0.4 * cm)]
    rosca, barras = graficos()
    s += [Table([[Image(rosca, width=7.4 * cm, height=6 * cm), Image(barras, width=8.6 * cm, height=6.2 * cm)]],
                colWidths=[W / 2, W / 2])]
    s += [Spacer(1, 0.3 * cm),
          Paragraph(f"<b>{len(ACHADOS)} achados</b>: nenhum crítico nem alto. Os dados pessoais (média) e o POST de outro "
                    f"site (baixa) foram corrigidos antes da publicação e o container agora roda sem root (baixa). "
                    "<b>Nenhum aberto</b>; 1 risco aceito por decisão do SPEC (sem login).", P),
          PageBreak()]

    # c) Pontos fortes e fracos
    s += [Paragraph("Pontos fortes", H1)]
    for titulo, ev in PONTOS_FORTES:
        s += [Paragraph(f'<font color="{COR["ponto forte"]}"><b>✔ {titulo}</b></font> — {esc(ev)}', P),
              Spacer(1, 3)]
    s += [Paragraph("Pontos fracos (riscos centrais)", H2),
          Paragraph("1. O app confia na rede: sem login, a defesa contra páginas maliciosas no navegador é a "
                    "porta no loopback + Host validado + bloqueio de escrita vinda de outro site (#1).", P),
          Paragraph("2. A cópia pública nasce da privada: sem a limpeza (#2), dados pessoais iriam junto.", P),
          Paragraph("3. Container rodava como root — corrigido (#3); falta só conferir no Windows.", P),
          Paragraph("Categorias do prompt que não se aplicam", H2)]
    for cat, why in NAO_SE_APLICA:
        s += [Paragraph(f"<b>{cat}</b> — {esc(why)}", P), Spacer(1, 2)]
    s += [PageBreak()]

    # d) Tabela detalhada
    s += [Paragraph("Achados detalhados", H1)]
    for cat in dict.fromkeys(a["cat"] for a in ACHADOS):
        rows = [["Sev.", "Arquivo:linha", "Descrição", "Status"]]
        for a in [x for x in ACHADOS if x["cat"] == cat]:
            rows.append([chip(a["sev"]), Paragraph(esc(a["arq"]), SMALL),
                         Paragraph(f"<b>#{a['id']} {esc(a['titulo'])}</b><br/>{esc(a['desc'])}"
                                   f"<br/><i>Correção:</i> {esc(a['fix'])}", SMALL),
                         Paragraph(a["status"], SMALL)])
        tt = Table(rows, colWidths=[2.7 * cm, 3.4 * cm, W - 8.2 * cm, 2.1 * cm], repeatRows=1)
        tt.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "DV-B", 8.5),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6"))]))
        s += [KeepTogether([Paragraph(cat, H2), tt]), Spacer(1, 0.2 * cm)]
    s += [Paragraph("Trechos de código (antes da correção)", H2)]
    for a in ACHADOS:
        s += [KeepTogether([Paragraph(f"#{a['id']} · {esc(a['arq'])}", SMALL), Preformatted(a["trecho"], CODE, maxLineLength=100, newLineChars=""),
                            Spacer(1, 4)])]
    s += [PageBreak()]

    # e) Recomendações + checklist
    s += [Paragraph("Recomendações priorizadas", H1)]
    for p, txt in RECOMENDACOES:
        s += [Paragraph(f"<b>{p}</b> — {esc(txt)}", P), Spacer(1, 3)]
    s += [Paragraph("Checklist antes do deploy", H2)]
    ck = Table([["Item", "Situação"]] + [[Paragraph(esc(a), SMALL), Paragraph(esc(b), SMALL)] for a, b in CHECKLIST],
               colWidths=[W * 0.5, W * 0.5])
    ck.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "DV-B", 8.5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E7EB")),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6"))]))
    s += [ck, PageBreak()]

    # f) Issues
    s += [Paragraph("Issues para o GitHub", H1),
          Paragraph("Só os achados ainda abertos viram issue; os corrigidos já estão nesta versão. "
                    "Nenhum achado é explorável a ponto de pedir advisory privado.", P), Spacer(1, 6)]
    if not abertos:
        s += [Paragraph("<b>Nenhuma issue em aberto:</b> todos os achados acionáveis foram corrigidos nesta versão.", P)]
    for n, a in enumerate(abertos, 1):
        s += [Preformatted(issue_md(n, a), CODE, maxLineLength=100, newLineChars=""), Spacer(1, 8)]

    doc.build(s, onFirstPage=lambda c, d: None, onLaterPages=cabecalho)


if __name__ == "__main__":
    montar()
    print(OUT)
