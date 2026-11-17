"""Gera docs/security-audit/relatorio-auditoria-seguranca-v1.10.pdf (pt-BR): auditoria da atualização v1.10.

Uso (ambiente isolado, nada global):
    python -m venv .venv-audit && .venv-audit/bin/pip install reportlab matplotlib
    .venv-audit/bin/python docs/security-audit/gerar_relatorio_v110.py

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

OUT = Path(__file__).resolve().parent / "relatorio-auditoria-seguranca-v1.10.pdf"
PROJETO = "Painel de Estudos"
TITULO = f"Relatório de Auditoria de Segurança — {PROJETO} v1.10"
DATA = date(2026, 11, 17)

COR = {"crítica": "#B91C1C", "alta": "#EA580C", "média": "#D97706", "baixa": "#2563EB",
       "informativa": "#64748B", "ponto forte": "#059669"}
ORDEM = ["crítica", "alta", "média", "baixa", "informativa"]

# --- Achados verificados ------------------------------------------------------
# status: "corrigido" (nesta versão), "aberto" (vira issue), "aceito" (risco aceito por decisão do SPEC)
ACHADOS = [
    {
        "id": 1, "cat": "Dados privados (cópia pública)", "sev": "baixa", "status": "corrigido",
        "arq": "SPEC.md, CLAUDE.md, testes novos",
        "titulo": "Nomes reais e referências pessoais na atualização exportada",
        "desc": "A exportação trouxe o nome do dono e do hub pessoal (D45), \"autorizado por mim\" (D52), a nota sobre o item "
                "de pendências privadas (D50/D51) e os nomes reais das disciplinas nos testes novos.",
        "trecho": "D45 | My private hub (<nome do repo>) ...\n_topics(seeded, \"<disciplina real>\")",
        "fix": "SPEC e CLAUDE.md reescritos de forma genérica (\"um hub pessoal\", \"autorizado pelo dono\"); testes com os "
               "nomes fictícios do seed público. Conferido por grep, texto do PDF e OCR dos prints novos ou refeitos.",
        "impacto": "Exposição de nomes reais e do hub privado.",
        "aceite": ["grep sem resultados fora do crédito de autor no README", "OCR e texto do PDF sem dados reais"],
    },
    {
        "id": 2, "cat": "Dependências (só desenvolvimento)", "sev": "informativa", "status": "aceito",
        "arq": "frontend/package.json (vite, vitest → picomatch)",
        "titulo": "picomatch com ReDoS (GHSA-fc5q-39xc-vjpf) nas ferramentas de build",
        "desc": "O npm audit aponta picomatch 4.0.7 dentro do vite e do vitest. É ferramenta de desenvolvimento: não vai "
                "para o pacote do app (npm audit --omit=dev: 0) e só lê padrões de arquivo do próprio projeto.",
        "trecho": "npm audit --omit=dev → found 0 vulnerabilities",
        "fix": "Nenhuma ação agora; atualizar o vite quando sair a versão corrigida (mudar dependência pede o OK do dono).",
        "impacto": "—", "aceite": [],
    },
    {
        "id": 3, "cat": "Entrada não confiável (imagens)", "sev": "informativa", "status": "aceito",
        "arq": "backend/app/agent/router.py",
        "titulo": "Prints na conversa com o agente (D52)",
        "desc": "Até 3 imagens por mensagem, só PNG/JPG/WebP/GIF (SVG e PDF recusados), até 8 MB cada; o servidor reabre "
                "e converte cada uma com o Pillow (reduz a 1280 px, JPEG) antes de mandar ao modelo local. A imagem não "
                "fica salva: a conversa guarda só o texto e uma marca.",
        "trecho": "data:image/svg+xml → 422; PNG quebrado → 422 (bad_image)",
        "fix": "Nenhuma ação agora.",
        "impacto": "—", "aceite": [],
    },
    {
        "id": 4, "cat": "Isolamento / autenticação", "sev": "informativa", "status": "aceito",
        "arq": "docker-compose.yml, backend/app/main.py",
        "titulo": "Sem login, por decisão do SPEC (D1); iframe só do próprio app e do hub local",
        "desc": "Igual às versões anteriores: porta só no loopback, Host validado e bloqueio de escrita de outro site, "
                "conferidos também nas rotas novas. O CSP libera iframe só para o próprio app e localhost:8100 (D45).",
        "trecho": '- "127.0.0.1:8000:8000"',
        "fix": "Nenhuma ação agora.",
        "impacto": "—", "aceite": [],
    },
]

PONTOS_FORTES = [
    ("Porta só no loopback", "docker-compose.yml publica 127.0.0.1:8000; nada exposto na rede."),
    ("Host validado (DNS rebinding)", "Host: evil.com → 400 em /api/review."),
    ("Escrita só da própria página, rotas novas incluídas", "POST /api/agent/question-sets/subject e /api/agent/chat "
     "com Origin externo → 403."),
    ("Imagens verificadas", "Só tipos de imagem; SVG/PDF → 422; arquivo quebrado → 422; reconvertidas no servidor."),
    ("Nada apagado sem regra", "Tema com histórico não sai (409); tarefa passada para outro dia deixa rastro."),
    ("Migrações só acrescentam", "carried_to e topic_ids são colunas novas; a de carried_to salva uma cópia do banco "
     "antes de corrigir o passado."),
    ("Notion só leitura nas questões da disciplina", "As páginas são lidas na hora; nada é gravado no tema nem no Notion."),
    ("Cabeçalhos de segurança", "CSP 'self' com frame-ancestors só do app e do hub local, nosniff, no-referrer."),
    ("Sem sinks de XSS", "Nenhum dangerouslySetInnerHTML, innerHTML, eval, new Function ou window.open no que mudou."),
    ("Sem segredos", "Busca por padrões (ntn_, secret_, sk-, ghp_, AKIA): nenhum resultado no que mudou."),
    ("Dependências do app limpas", "pip-audit: nenhuma vulnerabilidade; npm audit --omit=dev: 0."),
    ("CI", "GitHub Actions em todo pull request: ruff + pytest (148 testes) e tsc + vitest (30) + build."),
]

NAO_SE_APLICA = [
    ("1. Banco sem tranca (tenant)", "App de um usuário só, sem contas nem tenants (SPEC D1)."),
    ("2. Permissão no navegador", "Não existem papéis no frontend nem no backend."),
    ("3. IDOR", "Todo objeto pertence ao único usuário; as rotas de curso não alcançam a faculdade (v1.8)."),
    ("4. Chaves expostas", "Aplicável e verificado: nenhum achado (ver pontos fortes)."),
    ("5. XSS", "Aplicável e verificado: nenhum achado (ver pontos fortes)."),
]

RECOMENDACOES = [
    ("P2", "Atualizar o vite quando sair a versão com o picomatch corrigido."),
    ("P3", "Ativar Dependabot ou rodar npm audit e pip-audit a cada atualização."),
    ("P3", "A cada nova versão pública: repetir grep + OCR dos prints e trocar os nomes reais nos testes novos."),
]

CHECKLIST = [
    ("Rodei o prompt e li o PDF inteiro", "Para o dono fazer: ler este relatório."),
    ("Todo endpoint com ID valida o dono", "Não se aplica: um usuário só."),
    ("Toda listagem filtra por usuário/tenant", "Não se aplica: sem tenants."),
    ("Permissão escondida no front é conferida no servidor", "Não se aplica: sem papéis."),
    ("Nenhum segredo no código, bundle, compose ou CI", "OK: verificado."),
    ("Busca no histórico git e revogação", "OK: o histórico público só tem as versões fictícias; nada a revogar."),
    ("Input validado antes de virar HTML", "OK: React escapa; imagens validadas e reconvertidas no servidor."),
    ("Supabase: RLS e service_role", "Não se aplica: SQLite local."),
    ("Achados viraram issue ou advisory", "Achado acionável corrigido; picomatch aceito (só desenvolvimento)."),
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
          Paragraph("Atualização da cópia pública painel-de-estudos da v1.8 para a v1.10 (dados fictícios), antes do push: "
                    "backend FastAPI + SQLAlchemy + SQLite, frontend React + Vite + TypeScript, Dockerfile, "
                    "docker-compose, bundle compilado, prints e guia em PDF. Foco no que mudou desde a v1.8: resumo para o hub, "
                    "tarefas que passam de dia, Revisão, questões da disciplina (Notion) e prints na conversa.", P),
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
          Paragraph(f"<b>{len(ACHADOS)} achados</b>: nenhum crítico, alto ou médio. Os nomes reais e as referências "
                    "pessoais (baixa) foram corrigidos antes da publicação. <b>Nenhum aberto</b>; 3 informativos aceitos "
                    "(picomatch só no build, imagens na conversa, sem login).", P),
          PageBreak()]

    # c) Pontos fortes e fracos
    s += [Paragraph("Pontos fortes", H1)]
    for titulo, ev in PONTOS_FORTES:
        s += [Paragraph(f'<font color="{COR["ponto forte"]}"><b>✔ {titulo}</b></font> — {esc(ev)}', P),
              Spacer(1, 3)]
    s += [Paragraph("Pontos fracos (riscos centrais)", H2),
          Paragraph("1. O app confia na rede: sem login, a defesa contra páginas maliciosas no navegador é a "
                    "porta no loopback + Host validado + bloqueio de escrita vinda de outro site (#4).", P),
          Paragraph("2. A cópia pública nasce da privada: sem a limpeza (#1), nomes reais iriam junto nos testes novos.", P),
          Paragraph("3. Faculdade e cursos usam as mesmas tabelas: a trava das rotas de cursos é o que protege a "
                    "graduação (ver pontos fortes).", P),
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
