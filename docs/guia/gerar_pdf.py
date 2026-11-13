"""Gera docs/guia/GUIA.pdf a partir da seção em português do docs/GUIA.md, com os prints de docs/guia/img.

Uso (precisa de: pip install markdown playwright && playwright install chromium):
    python docs/guia/gerar_pdf.py

Os prints são tirados do app rodando (light mode, 1440×900). Para trocar um print, substitua o PNG
com o mesmo nome e rode de novo.
"""

import base64
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
GUIDE = HERE.parent / "GUIA.md"
OUT = HERE / "GUIA.pdf"

# Print colocado logo depois de cada título (### ...) da seção em português
SHOTS = {
    "5. Usando": [
        ("01-painel.png", "Painel: próxima prova, horas, próxima ação, cronômetro e o agente à direita."),
        ("02-gerar-questoes.png", "Gerar questões: disciplina, tema, texto de um módulo e número de alternativas."),
        ("03-questao.png", "Questão respondida: a correta fica marcada, com a explicação embaixo."),
        ("04-disciplinas.png", "Gerenciar → Disciplinas e temas."),
        ("05-provas.png", "Gerenciar → Provas e prazos."),
        ("06-curso.png", "Gerenciar → Semestres e curso."),
        ("07-acc.png", "Gerenciar → Atividades complementares."),
        ("09-provas-estudo.png", "Estudo → Provas e prazos: marcar como feito (com confirmação) e lançar o resultado."),
        ("10-historico.png", "Estudo → Histórico: evolução por tema, erros por status e refazer."),
        ("11-desempenho.png", "Estudo → Desempenho: passe o mouse num ponto para ler; clique para abrir o teste."),
        ("12-cards.png", "Estudo → Cards: gerar dos pontos fracos, de prints ou de vídeo; revisar por tema."),
    ],
    "3. LM Studio, uma vez só": [
        ("08-configuracoes.png", "Gerenciar → Configurações: endereço do modelo e modelo padrão."),
    ],
}

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm; }
body { font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; font-size: 10.5pt; line-height: 1.5;
       color: #0f172a; }
h1 { font-size: 22pt; margin: 0 0 4mm; }
.sub { color: #475569; margin: 0 0 8mm; }
h3 { font-size: 13.5pt; margin: 7mm 0 2mm; padding-top: 2mm; border-top: 1px solid #e2e8f0; color: #5b21b6; }
h3:first-of-type { border-top: 0; }
code { background: #f1f5f9; padding: 0 3px; border-radius: 3px; font-size: 9.5pt; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt; margin: 2mm 0; }
th, td { border: 1px solid #e2e8f0; padding: 4px 6px; text-align: left; vertical-align: top; }
th { background: #f8fafc; }
figure { margin: 3mm 0 5mm; break-inside: avoid; }
figure img { width: 100%; border: 1px solid #e2e8f0; border-radius: 6px; }
figcaption { font-size: 9pt; color: #475569; margin-top: 1mm; }
li { margin: 1mm 0; }
"""


def portuguese_section(md: str) -> str:
    part = md.split("## PORTUGUÊS", 1)[1]
    return part.strip()


def img_tag(name: str, caption: str) -> str:
    data = base64.b64encode((HERE / "img" / name).read_bytes()).decode()
    return f'<figure><img src="data:image/png;base64,{data}" alt="{caption}"><figcaption>{caption}</figcaption></figure>'


def build_html() -> str:
    body = markdown.markdown(portuguese_section(GUIDE.read_text(encoding="utf-8")), extensions=["tables"])
    for title, shots in SHOTS.items():
        marker = f"<h3>{title}</h3>"
        if marker in body:
            # Prints entram no fim da seção (antes do próximo título)
            start = body.index(marker) + len(marker)
            nxt = body.find("<h3>", start)
            nxt = len(body) if nxt == -1 else nxt
            body = body[:nxt] + "".join(img_tag(n, c) for n, c in shots) + body[nxt:]
    return (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            "<h1>Guia do Painel de Estudos</h1><p class='sub'>Como ligar, configurar e usar. "
            "Versão em PDF da seção em português do docs/GUIA.md.</p>"
            f"{body}</body></html>")


def main() -> None:
    html = build_html()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="load")
        page.pdf(path=str(OUT), format="A4", print_background=True, display_header_footer=True,
                 header_template="<span></span>",
                 footer_template="<div style='font-size:8pt;color:#64748b;width:100%;text-align:center'>"
                                 "Guia do Painel de Estudos · página <span class='pageNumber'></span> de "
                                 "<span class='totalPages'></span></div>",
                 margin={"top": "18mm", "bottom": "20mm", "left": "16mm", "right": "16mm"})
        browser.close()
    print(OUT)


if __name__ == "__main__":
    main()
