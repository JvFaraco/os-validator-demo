#!/usr/bin/env python3
"""Gera o banner do README (docs/readme/banner.png).

Mesma identidade do README do perfil e do portfólio: fundo azul-marinho,
amarelo de destaque, DM Sans e Fira Code (OFL, versionadas em tools/fonts/,
então o resultado é igual em qualquer sistema). Os números do painel saem do
gabarito e da rodada versionada do Claude Haiku 5.5, não de texto digitado.

Dependência de desenvolvimento: Pillow.

    python tools/render_readme.py
"""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]
FONTES = RAIZ / "tools" / "fonts"
DESTINO = RAIZ / "docs" / "readme" / "banner.png"

FUNDO, PAINEL, BORDA = "#0a0f1e", "#111a2d", "#29364d"
TEXTO, FRACO, AMARELO = "#e2e8f0", "#a1aec5", "#ffc72c"
VERDE, VERMELHO, TRILHO = "#83c6a2", "#ed746c", "#1c2740"

ESCALA = 2  # desenha em 2x para o texto sair nítido em tela de alta densidade
LARGURA, ALTURA = 1200, 380


@lru_cache(maxsize=None)
def fonte(tamanho: int, peso: int = 400, mono: bool = False) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTES / ("FiraCode.ttf" if mono else "DMSans.ttf")), tamanho * ESCALA)
    f.set_variation_by_axes([peso] if mono else [min(tamanho, 40), peso])
    return f


def numeros() -> dict:
    gabarito = yaml.safe_load((RAIZ / "data" / "gabarito.yaml").read_text(encoding="utf-8"))
    por_caminho = Counter(g["decisao"] for g in gabarito.values())
    haiku = json.loads((RAIZ / "resultados" / "avaliacao-anthropic-claude-haiku-5-5.json").read_text(encoding="utf-8"))
    return {
        "total": len(gabarito),
        "pronta": por_caminho["PRONTA_PARA_VALIDACAO"],
        "correcao": por_caminho["PRECISA_CORRECAO"],
        "revisao": por_caminho["REVISAO_HUMANA"],
        "acertos": haiku["metricas"]["decisao"]["acertos"],
        "chamadas": haiku["uso"]["chamadas_ia"],
        "custo": haiku["uso"]["custo_estimado_usd"],
    }


def main() -> int:
    n = numeros()
    s = ESCALA
    img = Image.new("RGB", (LARGURA * s, ALTURA * s), FUNDO)
    d = ImageDraw.Draw(img)

    def texto(xy, conteudo, f, cor):
        d.text((xy[0] * s, xy[1] * s), conteudo, font=f, fill=cor)

    def largura(conteudo, f):
        return d.textlength(conteudo, font=f) / s

    # faixa amarela embaixo, como no banner do perfil
    d.rectangle((0, (ALTURA - 3) * s, LARGURA * s, ALTURA * s), fill=AMARELO)

    # lado esquerdo: nome do projeto e a ideia em uma linha
    texto((48, 34), "// os-validator-demo", fonte(24, 600, mono=True), AMARELO)
    titulo = fonte(66, 700)
    texto((44, 76), "Validador de O.S.", titulo, TEXTO)
    texto((44, 150), "com IA", titulo, AMARELO)
    texto((48, 250), "Regras primeiro. IA só na nota.", fonte(30, 500), TEXTO)
    texto((48, 288), "Quem aprova é uma pessoa.", fonte(30, 500), TEXTO)
    texto((48, 336), "Python · Claude Haiku 5.5 · JSON Schema · dados fictícios", fonte(17, mono=True), FRACO)

    # lado direito: o resultado da rodada, num painel no estilo do terminal do perfil
    x0, y0, x1, y1 = 676, 46, 1160, 332
    d.rounded_rectangle((x0 * s, y0 * s, x1 * s, y1 * s), radius=14 * s, fill=PAINEL, outline=BORDA, width=2 * s)
    d.line((x0 * s, (y0 + 44) * s, x1 * s, (y0 + 44) * s), fill=BORDA, width=s)
    for i, cor in enumerate(("#ed746c", "#ffc72c", "#83c6a2")):
        cx = x0 + 26 + i * 21
        d.ellipse(((cx - 5) * s, (y0 + 18) * s, (cx + 4) * s, (y0 + 27) * s), fill=cor)
    texto((x0 + 96, y0 + 11), f"{n['total']} O.S. fictícias, rótulo à mão", fonte(17, mono=True), FRACO)

    linhas = [
        ("pronta para validação", n["pronta"], VERDE),
        ("volta ao técnico", n["correcao"], VERMELHO),
        ("vai para revisão humana", n["revisao"], AMARELO),
    ]
    rotulo, valor = fonte(19, 500), fonte(22, 600, mono=True)
    trilho_x0, trilho_x1 = x0 + 26, x1 - 26
    for i, (nome, qtd, cor) in enumerate(linhas):
        y = y0 + 64 + i * 58
        texto((trilho_x0, y), nome, rotulo, TEXTO)
        numero = str(qtd)
        texto((trilho_x1 - largura(numero, valor), y - 2), numero, valor, cor)
        yb = y + 32
        d.rounded_rectangle((trilho_x0 * s, yb * s, trilho_x1 * s, (yb + 8) * s), radius=4 * s, fill=TRILHO)
        fim = trilho_x0 + (trilho_x1 - trilho_x0) * qtd / n["total"]
        d.rounded_rectangle((trilho_x0 * s, yb * s, fim * s, (yb + 8) * s), radius=4 * s, fill=cor)

    custo = f"{n['custo']:.3f}".replace(".", ",")
    rodape = f"Haiku 5.5 · {n['acertos']}/{n['total']} certas · US$ {custo}"
    texto((trilho_x0, y1 - 40), rodape, fonte(17, 500, mono=True), VERDE)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    img.resize((LARGURA * 2, ALTURA * 2), Image.LANCZOS).save(DESTINO, optimize=True)
    print(f"{DESTINO.relative_to(RAIZ)}: {DESTINO.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
