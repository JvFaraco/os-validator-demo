#!/usr/bin/env python3
"""Grava a prévia da demo interativa para o README.

Gera docs/readme/demo.gif (em loop) e docs/readme/demo.png (um quadro da mesma
gravação, para quem pediu menos movimento). Mesmo método do GIF do mapa no
README do perfil: stop-motion. O cursor desenhado anda um passo por quadro, o
que a página anima sozinha é capturado em tempo real e as pausas são um quadro
segurado na tela.

A página é a de docs/, servida localmente, com os dados fictícios de
docs/dados.json. Dependências de desenvolvimento: Playwright (Chromium) e Pillow.

    python tools/record_demo_preview.py
"""

from __future__ import annotations

import functools
import http.server
import io
import threading
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
GIF = DOCS / "readme" / "demo.gif"
PNG = DOCS / "readme" / "demo.png"

VIEWPORT = {"width": 1280, "height": 760}
LARGURA = 1000          # largura do GIF; o README mostra perto de 880 px
CORES = 128             # a página é de cores chapadas: 128 bastam e o arquivo cai bastante
PASSO_MS = 50           # um passo do cursor por quadro
PAUSA_FINAL_MS = 1600

CURSOR = """
(() => {
  const c = document.createElement('div');
  c.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24"><path d="M4 2l15 11-6.5 1.2L16 21l-3 1.4-3.4-6.6L4 20z" fill="#fff" stroke="#0b0f14" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, { position: 'fixed', left: '0', top: '0', zIndex: 2147483647, pointerEvents: 'none',
    transform: 'translate(-100px,-100px)', filter: 'drop-shadow(0 2px 3px rgba(0,0,0,.45))' });
  const ring = document.createElement('div');
  Object.assign(ring.style, { position: 'fixed', width: '34px', height: '34px', margin: '-17px 0 0 -17px', borderRadius: '50%',
    border: '2px solid #ffc72c', zIndex: 2147483646, pointerEvents: 'none', opacity: '0', left: '0', top: '0' });
  document.body.append(ring, c);
  addEventListener('mousemove', (e) => { c.style.transform = `translate(${e.clientX - 3}px, ${e.clientY - 2}px)`; }, true);
  addEventListener('mousedown', (e) => {
    ring.style.left = e.clientX + 'px'; ring.style.top = e.clientY + 'px';
    ring.animate([{ opacity: .9, transform: 'scale(.4)' }, { opacity: 0, transform: 'scale(1.4)' }], { duration: 450, easing: 'ease-out' });
  }, true);
})();
"""


class Filme:
    """Quadros e quanto tempo cada um fica na tela."""

    def __init__(self, pagina):
        self.pagina, self.quadros = pagina, []
        self.mouse = (VIEWPORT["width"] * .55, VIEWPORT["height"] * .5)
        self.marcas: dict[str, int] = {}

    def foto(self, duracao):
        self.quadros.append([self.pagina.screenshot(), duracao])

    def segura(self, ms):
        self.foto(ms)

    def ao_vivo(self, ms):
        """Tempo real: a página anima sozinha; cada quadro dura até o próximo."""
        inicio = ultimo = time.perf_counter()
        while (time.perf_counter() - inicio) * 1000 < ms:
            png = self.pagina.screenshot()
            agora = time.perf_counter()
            if self.quadros and self.quadros[-1][1] is None:
                self.quadros[-1][1] = round((agora - ultimo) * 1000)
            self.quadros.append([png, None])
            ultimo = agora
        self.quadros[-1][1] = round((time.perf_counter() - ultimo) * 1000)

    def move(self, x, y, passos=12):
        x0, y0 = self.mouse
        for i in range(1, passos + 1):
            k = i / passos
            k = 4 * k ** 3 if k < .5 else 1 - (-2 * k + 2) ** 3 / 2
            self.pagina.mouse.move(x0 + (x - x0) * k, y0 + (y - y0) * k)
            self.foto(PASSO_MS)
        self.mouse = (x, y)

    def clica(self, seletor, passos=12):
        caixa = self.pagina.locator(seletor).bounding_box()
        x, y = caixa["x"] + min(caixa["width"] * .5, 120), caixa["y"] + caixa["height"] * .5
        self.move(x, y, passos)
        self.pagina.mouse.click(x, y)

    def marca(self, nome):
        self.marcas[nome] = len(self.quadros) - 1


def gravar(url: str) -> Filme:
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        contexto = navegador.new_context(viewport=VIEWPORT, color_scheme="dark", reduced_motion="no-preference")
        pagina = contexto.new_page()
        pagina.add_init_script(f"addEventListener('DOMContentLoaded', () => {{ {CURSOR} }})")
        pagina.goto(url + "#OS-0007/haiku/sanitizacao")
        pagina.wait_for_selector("#app:not([hidden])")
        # o título da página fica fora do quadro: a prévia começa na escolha da O.S.
        pagina.evaluate("scrollTo(0, document.getElementById('app').getBoundingClientRect().top + scrollY - 14)")
        pagina.wait_for_timeout(1300)
        filme = Filme(pagina)
        pagina.mouse.move(*filme.mouse)
        filme.segura(2600)                                  # OS-0007: nome e telefone viram marcadores
        filme.marca("parado")

        filme.clica('.destaque[data-os="OS-0019"]', 14)
        filme.ao_vivo(900)                                  # a O.S. percorre o fluxo e sai nas regras
        filme.segura(2000)

        filme.clica('.destaque[data-os="OS-0029"]', 10)
        filme.ao_vivo(900)                                  # sai na guarda de comando, sem chamar a IA
        filme.segura(2000)

        filme.clica('input[name="provedor"][value="falso"] + span', 14)
        filme.ao_vivo(500)
        filme.clica('.destaque[data-os="OS-0036"]', 12)
        filme.ao_vivo(900)                                  # o provedor falso aprova errado: não bateu
        filme.segura(2200)

        filme.clica('input[name="provedor"][value="haiku"] + span', 12)
        filme.ao_vivo(900)                                  # o Haiku se abstém na mesma O.S.
        filme.quadros[-1][1] += PAUSA_FINAL_MS
        navegador.close()
        return filme


def montar(filme: Filme) -> None:
    imagens = []
    for png, _ in filme.quadros:
        img = Image.open(io.BytesIO(png)).convert("RGB")
        imagens.append(img.resize((LARGURA, round(img.height * LARGURA / img.width)), Image.LANCZOS))
    duracoes = [max(20, d) for _, d in filme.quadros]

    # Uma paleta só para todos os quadros: o que não mexeu fica idêntico e cada
    # quadro guarda só o que mudou.
    amostras = imagens[:: max(1, len(imagens) // 12)] + [imagens[-1]]
    mosaico = Image.new("RGB", (LARGURA, imagens[0].height * len(amostras)))
    for i, img in enumerate(amostras):
        mosaico.paste(img, (0, i * img.height))
    paleta = mosaico.quantize(colors=CORES, method=Image.Quantize.FASTOCTREE)
    quadros = [img.quantize(palette=paleta, dither=Image.Dither.NONE) for img in imagens]
    GIF.parent.mkdir(parents=True, exist_ok=True)
    quadros[0].save(GIF, save_all=True, append_images=quadros[1:], duration=duracoes, loop=0, optimize=True)
    imagens[filme.marcas["parado"]].save(PNG, optimize=True)
    print(f"{GIF.relative_to(RAIZ)}: {GIF.stat().st_size // 1024} KB, {len(imagens)} quadros, {sum(duracoes) / 1000:.1f} s")
    print(f"{PNG.relative_to(RAIZ)}: {PNG.stat().st_size // 1024} KB")


class _Silencioso(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main() -> int:
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Silencioso, directory=str(DOCS)))
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        montar(gravar(f"http://127.0.0.1:{servidor.server_address[1]}/"))
    finally:
        servidor.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
