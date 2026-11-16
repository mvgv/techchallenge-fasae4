"""Gera docs/relatorio-tecnico.pdf a partir de docs/relatorio-tecnico.md.

Usa markdown-it (Markdown para HTML) e WeasyPrint (HTML para PDF), ambos já na imagem Docker.
As imagens ficam em docs/img/. Links relativos para outros arquivos do repositório viram texto simples,
porque no PDF eles não apontam para lugar nenhum.

Uso (no Docker, montando docs/ e scripts/):
    docker compose run --rm --no-deps -v "${PWD}/docs:/app/docs" -v "${PWD}/scripts:/app/scripts" \
        api python scripts/build_report_pdf.py
"""
# ruff: noqa: E501  (o CSS embutido tem linhas longas)
from __future__ import annotations

import re
import sys
from pathlib import Path

from markdown_it import MarkdownIt
from weasyprint import HTML

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SRC = DOCS / "relatorio-tecnico.md"
OUT = DOCS / "relatorio-tecnico.pdf"

CSS = """
@page {
  size: A4; margin: 1.8cm 1.6cm 2cm 1.6cm;
  @bottom-center { content: "MedWatch · Relatório técnico · página " counter(page) " de " counter(pages);
                   font-size: 8pt; color: #666; }
}
@page paisagem {
  size: A4 landscape; margin: 1.5cm 1.5cm 1.8cm 1.5cm;
  @bottom-center { content: "MedWatch · Relatório técnico · página " counter(page) " de " counter(pages);
                   font-size: 8pt; color: #666; }
}
.paisagem { page: paisagem; }
html { font-family: "DejaVu Sans", "Liberation Sans", Arial, sans-serif; font-size: 9.6pt; line-height: 1.38; color: #1a1a1a; }
h1 { font-size: 21pt; margin: 0 0 4pt; color: #0b3d6b; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; color: #0b3d6b; border-bottom: 1pt solid #0b3d6b; padding-bottom: 2pt; }
h3 { font-size: 11pt; margin: 12pt 0 4pt; color: #0b3d6b; }
h2, h3 { page-break-after: avoid; }
p { margin: 4pt 0 6pt; text-align: left; }
a { color: #0b5cad; text-decoration: none; overflow-wrap: anywhere; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8pt; background: #f1f3f5; padding: 0 2pt; overflow-wrap: anywhere; }
pre { font-size: 7.6pt; background: #f1f3f5; padding: 6pt; white-space: pre-wrap; overflow-wrap: anywhere; border-left: 2pt solid #0b3d6b; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; font-size: 7.6pt; margin: 6pt 0 10pt; }
th, td { border: 0.5pt solid #b8bec6; padding: 2.5pt 3.5pt; vertical-align: top; overflow-wrap: break-word; }
td code, td a { overflow-wrap: anywhere; }
th { background: #e6eef7; text-align: left; }
tr { page-break-inside: avoid; }
ul, ol { margin: 3pt 0 6pt 14pt; padding-left: 6pt; }
li { margin: 1.5pt 0; }
blockquote { margin: 6pt 0; padding: 3pt 8pt; border-left: 3pt solid #c9a227; background: #fbf7e6; }
img { display: block; max-width: 100%; height: auto; margin: 8pt auto 2pt; page-break-inside: avoid; }
img[alt^="Agachamento"] { max-height: 7.2cm; width: auto; }
img[alt^="Frame anotado"] { max-width: 52%; }
img[alt^="Painel geral"] { max-width: 72%; }
img[alt^="Risco ao longo"] { max-width: 80%; }
img[alt^="Transcrição"] { max-width: 72%; }
img[alt^="Sequência"] { max-width: 100%; }
p > em:only-child { display: block; text-align: center; color: #444; font-size: 8.4pt; margin-bottom: 8pt; }
"""

LINK_RELATIVO = re.compile(r"(?<!\!)\[([^\]]+)\]\((?!https?://|#|mailto:)([^)]+)\)")


def envolver_paisagem(html: str) -> str:
    """Põe em páginas na horizontal as seções com tabelas largas (modelos por tipo de dado; datasets)."""
    for inicio, fim in (("<h2>3. ", "<h2>4. "), ("<h3>5.4 ", "<p>Leitura sem maquiagem")):
        i = html.index(inicio)
        j = html.index(fim, i)
        html = html[:i] + '<div class="paisagem">' + html[i:j] + "</div>" + html[j:]
    return html


def build() -> Path:
    texto = SRC.read_text(encoding="utf-8")
    texto = LINK_RELATIVO.sub(r"\1", texto)
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    corpo = envolver_paisagem(md.render(texto))
    html = (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            f"<title>MedWatch: relatório técnico</title><style>{CSS}</style></head><body>{corpo}</body></html>")
    HTML(string=html, base_url=str(DOCS) + "/").write_pdf(str(OUT))
    return OUT


if __name__ == "__main__":
    out = build()
    print(f"gerado: {out} ({out.stat().st_size // 1024} KB)")
    sys.exit(0)
