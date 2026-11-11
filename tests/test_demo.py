"""A demo interativa (docs/) mostra o que o código faz, e não uma cópia que envelhece."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gerar_demo", RAIZ / "tools" / "gerar_demo.py")
gerar_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gerar_demo)

DADOS_DEMO = RAIZ / "docs" / "dados.json"
PAGINA = RAIZ / "docs" / "index.html"


def test_dados_da_demo_batem_com_o_codigo_e_as_rodadas():
    # montar() já para se o caminho reproduzido divergir da rodada salva
    atual = gerar_demo.serializar(gerar_demo.montar())
    assert DADOS_DEMO.read_text(encoding="utf-8") == atual, "rode: python tools/gerar_demo.py"


def test_demo_cobre_todas_as_os_e_os_tres_provedores():
    dados = json.loads(DADOS_DEMO.read_text(encoding="utf-8"))
    ids = sorted(p.stem.upper() for p in (RAIZ / "data" / "ordens").glob("os-*.json"))
    assert [o["id"] for o in dados["ordens"]] == ids
    assert {p["id"] for p in dados["provedores"]} == {"haiku", "sonnet", "falso"}
    assert all(set(o["por_provedor"]) == {"haiku", "sonnet", "falso"} for o in dados["ordens"])


def test_pagina_nao_carrega_nada_de_fora():
    html = PAGINA.read_text(encoding="utf-8")
    assert not re.search(r"<script[^>]+src=", html)
    assert not re.search(r"<link[^>]+stylesheet", html)
    assert 'fetch("dados.json"' in html
