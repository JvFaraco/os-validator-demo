"""Os números do README são reproduzíveis: a rodada versionada tem que bater com uma nova."""

from __future__ import annotations

import json

from validador import RESULTADOS
from validador.avaliacao import avaliar, carregar_gabarito
from validador.ia.falso import ProvedorFalso

from .conftest import ORDENS


def test_gabarito_cobre_todas_as_os_e_so_elas():
    ids = {json.loads(p.read_text(encoding="utf-8"))["id"] for p in ORDENS}
    assert set(carregar_gabarito()) == ids
    assert 30 <= len(ids) <= 40


def test_matriz_soma_o_total():
    r = avaliar(ProvedorFalso())
    assert sum(sum(linha.values()) for linha in r["matriz_confusao"].values()) == r["total_os"]


def test_resultado_versionado_do_provedor_falso_continua_valendo():
    versionado = json.loads((RESULTADOS / "avaliacao-falso.json").read_text(encoding="utf-8"))
    atual = avaliar(ProvedorFalso())
    for chave in ("metricas", "matriz_confusao", "erros", "casos"):
        assert atual[chave] == versionado[chave], chave
