"""Gera docs/security-audit/relatorio-auditoria-seguranca.pdf (pt-BR).

Uso (ambiente isolado, nada global):
    python -m venv .venv-audit && .venv-audit/bin/pip install reportlab matplotlib
    .venv-audit/bin/python docs/security-audit/gerar_relatorio.py

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

OUT = Path(__file__).resolve().parent / "relatorio-auditoria-seguranca.pdf"
PROJETO = "Painel de Estudos"
TITULO = f"Relatório de Auditoria de Segurança — {PROJETO}"
DATA = date(2026, 11, 12)

COR = {"crítica": "#B91C1C", "alta": "#EA580C", "média": "#D97706", "baixa": "#2563EB",
       "informativa": "#64748B", "ponto forte": "#059669"}
ORDEM = ["crítica", "alta", "média", "baixa", "informativa"]

# --- Achados verificados ------------------------------------------------------
# status: "corrigido" (nesta versão), "aberto" (vira issue), "aceito" (risco aceito por decisão do SPEC)
ACHADOS = [
    {
        "id": 1, "cat": "CSRF / isolamento de rede", "sev": "baixa", "status": "corrigido",
        "arq": "backend/app/main.py:52-62 (agent/router.py:270, learning.py:225, notion.py:263, google_calendar.py:269)",
        "titulo": "POST sem corpo podia ser disparado por outro site",
        "desc": "As escritas com corpo exigem JSON (text/plain, form e corpo sem Content-Type → 422), mas quatro "
                "rotas POST não têm corpo: marcar questão como ruim, montar o dia, sincronizar Notion e "
                "sincronizar Agenda. Um site aberto no navegador podia mandar fetch(..., {method:'POST', "
                "mode:'no-cors'}) para localhost:8000: o Host é permitido e a requisição é 'simples'. "
                "Prova com Chromium (Playwright): página em 127.0.0.2 disparou POST /api/learning/checklist/plan → 200. "
                "Exige o painel rodando e o atacante adivinhar a porta; o efeito é limitado (ações que o próprio "
                "usuário faria), por isso baixa.",
        "trecho": '@router.post("/checklist/plan")\ndef plan_day(day: date | None = Query(None), ...)',
        "fix": "Middleware block_cross_site_writes: em POST/PUT/PATCH/DELETE recusa (403) Sec-Fetch-Site diferente "
               "de same-origin/none e Origin fora de PAINEL_ALLOWED_HOSTS. Mesmo teste no Chromium agora → 403; "
               "a própria página continua 200 (tests/test_security.py::test_blocks_cross_site_writes).",
        "impacto": "Outro site podia gravar resultados no Notion, criar provas na agenda do painel ou marcar questões.",
        "aceite": ["POST com Sec-Fetch-Site cross-site/same-site → 403", "POST com Origin externo → 403",
                   "A página do painel e o vite dev (localhost:5173) continuam funcionando"],
    },
    {
        "id": 2, "cat": "Dados pessoais (cópia pública)", "sev": "média", "status": "corrigido",
        "arq": "backend/app/seed.py, SPEC.md, CLAUDE.md, docs/, prints e guia",
        "titulo": "Dados reais do dono na cópia exportada da versão privada",
        "desc": "A exportação da versão privada trazia nome do dono, instituição e polo, disciplinas reais, horas "
                "do histórico acadêmico, caminhos D:\\ do PC, hardware e relatórios internos. Num repositório "
                "público isso expõe dados pessoais e a rotina do dono.",
        "trecho": "institution=\"<instituição real>\", LOCATION=\"<polo real>\"",
        "fix": "Carga inicial 100% fictícia (Universidade Exemplo, Polo Centro, disciplinas e horas inventadas); "
               "ids das regras sem nome de faculdade (padrao_2026...); SPEC/CLAUDE.md sem caminhos, hardware ou "
               "nome; prints e guia refeitos com os dados fictícios; docs internos removidos. Conferido por grep e "
               "OCR de todas as imagens e do PDF.",
        "impacto": "Exposição de dados pessoais.",
        "aceite": ["grep por nome, instituição, caminhos e e-mail sem resultados", "OCR dos prints sem dados reais"],
    },
    {
        "id": 3, "cat": "Infraestrutura", "sev": "baixa", "status": "corrigido",
        "arq": "Dockerfile:23-26, backend/entrypoint.sh:7-16",
        "titulo": "Container roda como root",
        "desc": "A imagem final não define USER. Se alguém explorar o processo, ele tem root no container e "
                "escrita no volume ./data. A troca de usuário mexe nas permissões do volume no Docker Desktop do "
                "Windows e precisa ser testada numa máquina real antes.",
        "trecho": "FROM python:3.12-slim\n...\nCMD [\"/app/backend/entrypoint.sh\"]",
        "fix": "Usuário app (uid 10001) na imagem. O entrypoint começa como root só para dar chown em "
               "/app/data e /app/secrets e reexecuta como app com setpriv. Se a pasta montada ainda não aceitar "
               "escrita do app (algumas pastas do Windows), avisa no log e segue como root para o painel não "
               "parar. Simulado: pastas do host com dono root e banco antigo criado como root → API como "
               "uid=10001; pasta travada → aviso e root.",
        "impacto": "Processo comprometido dentro do container teria root e escrita direta no banco em ./data.",
        "aceite": ["Dockerfile define USER sem privilégio (uid fixo)",
                   "/app/data pertence a esse usuário; migrações rodam no start",
                   "`docker compose up` sobe com o volume ./data existente no Windows",
                   "`docker compose exec app id` não mostra uid=0"],
    },
    {
        "id": 4, "cat": "Isolamento / autenticação", "sev": "informativa", "status": "aceito",
        "arq": "docker-compose.yml:7",
        "titulo": "Sem login, por decisão do SPEC (D1)",
        "desc": "Qualquer processo ou usuário do mesmo PC acessa 127.0.0.1:8000. A barreira é a porta presa ao "
                "loopback + validação de Host + bloqueio de escrita vinda de outro site (#1). Aceito para app "
                "pessoal de um usuário.",
        "trecho": '- "127.0.0.1:8000:8000"',
        "fix": "Nenhuma ação agora.",
        "impacto": "—", "aceite": [],
    },
]

PONTOS_FORTES = [
    ("Porta só no loopback", "docker-compose.yml:7 publica 127.0.0.1:8000; nada exposto na rede."),
    ("Host validado (DNS rebinding)", "TrustedHostMiddleware (main.py:26); Host: evil.com → 400 contra o app rodando."),
    ("Escrita só da própria página", "JSON obrigatório nas escritas com corpo (sem Content-Type, text/plain → 422) "
     "e bloqueio de Sec-Fetch-Site/Origin externos (#1)."),
    ("Sem CORS", "Nenhum CORSMiddleware; outro site não lê as respostas da API."),
    ("Cabeçalhos de segurança", "CSP só 'self', frame-ancestors 'none', X-Frame-Options DENY, nosniff, no-referrer."),
    ("Sem SQL cru", "Acesso ao banco só pelo ORM SQLAlchemy; nenhum execute com f-string."),
    ("Sem sinks de XSS", "Nenhum dangerouslySetInnerHTML, innerHTML, eval, new Function, window.open ou href/src "
     "dinâmico em frontend/src; saída do modelo renderizada como texto."),
    ("Sem segredos", "Busca por padrões (ntn_, secret_, sk-, ghp_, github_pat_, AIza, GOCSPX-, chave privada, "
     "client_secret, refresh_token): só valores falsos dos testes (test_f5_integrations.py:176, 212). "
     "Repositório novo, sem histórico herdado; .env e secrets/ no .gitignore; .env.example sem valores."),
    ("Integrações sem apagar", "Notion só acrescenta blocos (PATCH children); Google recusa DELETE e só edita "
     "eventos com painel=1, numa agenda própria."),
    ("Arquivos estáticos seguros", "A rota SPA confere que o arquivo está dentro de frontend/dist (main.py:207); "
     "/../../etc/passwd e variantes codificadas devolvem o index.html."),
    ("Dependências limpas", "pip-audit -r requirements.txt: nenhuma vulnerabilidade; npm audit: 0."),
    ("Sem dados pessoais", "Carga fictícia; grep e OCR de prints e PDF sem nome, instituição, caminhos ou e-mail."),
]

NAO_SE_APLICA = [
    ("1. Banco sem tranca (tenant)", "App de um usuário só, sem contas nem tenants (SPEC D1). O isolamento real "
     "é de rede: loopback + Host + bloqueio de escrita de outro site."),
    ("2. Permissão no navegador", "Não existem papéis (isAdmin, canEdit) no frontend nem no backend."),
    ("3. IDOR", "Todas as rotas por ID (crud.py, agent/router.py, learning.py, course.py, overview.py, "
     "integrations/) foram percorridas: todo objeto pertence ao único usuário; não há dono a conferir."),
    ("4. Chaves expostas", "Aplicável e verificado: nenhum achado (ver pontos fortes)."),
    ("5. XSS", "Aplicável e verificado: nenhum achado (ver pontos fortes)."),
]

RECOMENDACOES = [
    ("P1", "Manter a correção #1 também na versão privada (PR de endurecimento)."),
    ("P2", "No Docker Desktop do Windows, conferir com `docker compose exec app id` que a API roda como "
     "uid=10001 e que não aparece o AVISO no log (#3)."),
    ("P3", "Ativar Dependabot ou rodar npm audit e pip-audit a cada atualização."),
    ("P3", "A cada nova versão pública: repetir a busca por segredos e dados pessoais (grep + OCR dos prints)."),
]

CHECKLIST = [
    ("Rodei o prompt e li o PDF inteiro", "Para o dono fazer: ler este relatório."),
    ("Todo endpoint com ID valida o dono", "Não se aplica: um usuário só."),
    ("Toda listagem filtra por usuário/tenant", "Não se aplica: sem tenants."),
    ("Permissão escondida no front é conferida no servidor", "Não se aplica: sem papéis."),
    ("Nenhum segredo no código, bundle, compose ou CI", "OK: verificado."),
    ("Busca no histórico git e revogação", "OK: repositório publicado com histórico novo; nada a revogar."),
    ("Input validado antes de virar HTML", "OK: React escapa; sem sinks de HTML."),
    ("Supabase: RLS e service_role", "Não se aplica: SQLite local."),
    ("Achados viraram issue ou advisory", "Todos corrigidos; nenhuma issue nem advisory em aberto."),
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
          Paragraph("Cópia pública painel-de-estudos (v1, dados fictícios), antes do primeiro push: "
                    "backend FastAPI + SQLAlchemy + SQLite, frontend React + Vite + TypeScript, Dockerfile, "
                    "docker-compose, bundle compilado, prints e guia em PDF. Todos os handlers de rota foram lidos.", P),
          Paragraph("<b>Stack detectada e como cada categoria foi mapeada</b>", H2),
          Paragraph("App local de um usuário, sem autenticação (SPEC D1), porta presa a 127.0.0.1. "
                    "(1) Isolamento: não há tenant; foi auditado o isolamento de rede (loopback, Host, CORS, CSRF). "
                    "(2) Permissão no navegador e (3) IDOR: não há papéis nem donos; todos os routers foram "
                    "percorridos para confirmar. (4) Chaves: código, compose, .env.example, histórico git e bundle. "
                    "(5) XSS: sinks no React e renderização da saída do modelo. Além das cinco, foram auditados "
                    "cabeçalhos HTTP, dependências (pip-audit, npm audit) e o container.", P),
          Paragraph("<b>Método</b>", H2),
          Paragraph("Leitura de código + testes contra o app rodando (curl e Playwright): Host forjado, "
                    "POST text/plain e sem Content-Type, POST de outro site no Chromium, travessia de caminho; "
                    "grep de segredos e dados pessoais; OCR dos prints e do PDF; pip-audit e npm audit.", P),
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
