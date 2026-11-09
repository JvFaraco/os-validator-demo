#!/usr/bin/env python3
"""Gera as imagens do README a partir da saída real do CLI.

Roda o comando com cores ANSI, converte para SVG (janela de terminal) e grava
em docs/. Sem dependências: o SVG é texto, e o GitHub o exibe direto.

    python tools/gerar_print.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from html import escape
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

IMAGENS = {
    "docs/analisar.svg": ["analisar", "data/ordens/os-0007.json"],
    "docs/avaliar.svg": ["avaliar"],
}

FONTE = 13
ALTURA_LINHA = 18
LARGURA_CHAR = 7.85
MARGEM = 18
BARRA = 34
FUNDO, TEXTO, FRACO = "#0d1117", "#e6edf3", "#8b949e"
CORES = {"31": "#ff7b72", "32": "#7ee787", "33": "#e3b341", "34": "#79c0ff", "35": "#d2a8ff", "36": "#56d4dd"}
ANSI = re.compile(r"\x1b\[([\d;]*)m")


def segmentos(linha: str):
    """Quebra uma linha com ANSI em (texto, cor, negrito)."""
    cor, negrito, pos = None, False, 0
    for m in ANSI.finditer(linha):
        if m.start() > pos:
            yield linha[pos:m.start()], cor, negrito
        for codigo in (m.group(1) or "0").split(";"):
            if codigo == "0":
                cor, negrito = None, False
            elif codigo == "1":
                negrito = True
            elif codigo == "2":
                cor = "fraco"
            elif codigo in CORES:
                cor = codigo
        pos = m.end()
    if pos < len(linha):
        yield linha[pos:], cor, negrito


def para_svg(comando: str, saida: str) -> str:
    linhas = [f"\x1b[2m$\x1b[0m {comando}", ""] + saida.rstrip("\n").splitlines()
    colunas = max(len(ANSI.sub("", l)) for l in linhas)
    largura = int(colunas * LARGURA_CHAR + 2 * MARGEM)
    altura = BARRA + len(linhas) * ALTURA_LINHA + MARGEM
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" role="img" aria-label="{escape(comando)}">',
        f'<rect width="{largura}" height="{altura}" rx="10" fill="{FUNDO}"/>',
        '<circle cx="20" cy="17" r="6" fill="#ff5f57"/><circle cx="40" cy="17" r="6" fill="#febc2e"/>'
        '<circle cx="60" cy="17" r="6" fill="#28c840"/>',
        f'<g font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, \'DejaVu Sans Mono\', monospace" '
        f'font-size="{FONTE}" fill="{TEXTO}" xml:space="preserve">',
    ]
    for i, linha in enumerate(linhas):
        y = BARRA + MARGEM + i * ALTURA_LINHA - 4
        spans = []
        for texto, cor, negrito in segmentos(linha):
            atributos = ""
            if cor == "fraco":
                atributos += f' fill="{FRACO}"'
            elif cor:
                atributos += f' fill="{CORES[cor]}"'
            if negrito:
                atributos += ' font-weight="700"'
            # espaço não separável: navegadores colapsam espaços repetidos em SVG
            spans.append(f"<tspan{atributos}>{escape(texto).replace(' ', '&#160;')}</tspan>")
        partes.append(f'<text x="{MARGEM}" y="{y}">{"".join(spans)}</text>')
    partes += ["</g>", "</svg>"]
    return "\n".join(partes) + "\n"


def main() -> int:
    ambiente = {**os.environ, "FORCE_COLOR": "1", "PYTHONIOENCODING": "utf-8"}
    ambiente.pop("NO_COLOR", None)
    for destino, args in IMAGENS.items():
        saida = subprocess.run(
            [sys.executable, "-m", "validador", *args, "--cor"],
            cwd=RAIZ, env=ambiente, capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout
        caminho = RAIZ / destino
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(para_svg("python -m validador " + " ".join(args), saida), encoding="utf-8")
        print(f"{destino}: {len(saida.splitlines())} linhas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
