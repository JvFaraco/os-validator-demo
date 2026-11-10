"""Os números do README são reproduzíveis: a rodada versionada tem que bater com uma nova."""

from __future__ import annotations

import json

import pytest

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


@pytest.mark.parametrize("arquivo", sorted(RESULTADOS.glob("avaliacao-*.json")), ids=lambda p: p.stem)
def test_relatorios_versionados_sao_coerentes_com_o_gabarito(arquivo):
    """Vale também para a rodada real, que não dá para refazer sem chave: as métricas
    gravadas têm que sair dos casos gravados, e os esperados têm que ser o gabarito atual."""
    r = json.loads(arquivo.read_text(encoding="utf-8"))
    gabarito = carregar_gabarito()
    casos = r["casos"]
    assert {c["id"] for c in casos} == set(gabarito)
    for c in casos:
        assert c["decisao_esperada"] == gabarito[c["id"]]["decisao"]
        assert c["combinacao_esperada"] == gabarito[c["id"]]["combinacao"]
    decisao = sum(c["decisao_esperada"] == c["decisao_obtida"] for c in casos)
    com_combinacao = [c for c in casos if c["combinacao_esperada"]]
    classificacao = sum(c["combinacao_esperada"] == c["combinacao_obtida"] for c in com_combinacao)
    assert r["metricas"]["decisao"]["acertos"] == decisao
    assert r["metricas"]["classificacao"]["acertos"] == classificacao
    assert r["metricas"]["classificacao"]["total"] == len(com_combinacao)


def test_resultado_versionado_do_provedor_falso_continua_valendo():
    versionado = json.loads((RESULTADOS / "avaliacao-falso.json").read_text(encoding="utf-8"))
    atual = avaliar(ProvedorFalso())
    for chave in ("metricas", "matriz_confusao", "erros", "casos"):
        assert atual[chave] == versionado[chave], chave
