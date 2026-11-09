"""Regras determinísticas: cada uma isolada, e todas contra o gabarito."""

from __future__ import annotations

import pytest

from validador.avaliacao import carregar_gabarito
from validador.modelos import Severidade
from validador.regras import CODIGOS, REGRAS, avaliar_regras


def codigos(ordem: dict) -> set[str]:
    return {a.codigo for a in avaliar_regras(ordem)}


def test_ha_oito_regras_e_codigos_batem():
    assert len(REGRAS) == len(CODIGOS) == 8


def test_os_limpa_nao_gera_achado(ordem_base):
    assert avaliar_regras(ordem_base) == []


@pytest.mark.parametrize("nota", ["", "   ", "Feito, ok."])
def test_nota_vazia_ou_curta_bloqueia(ordem_base, nota):
    ordem_base["nota_tecnico"] = nota
    (achado,) = avaliar_regras(ordem_base)
    assert achado.codigo == "NOTA_VAZIA" and achado.severidade is Severidade.BLOQUEIO


def test_retirada_sem_movimentacao_bloqueia_com_a_serie(ordem_base):
    ordem_base["movimentacoes_estoque"] = []
    (achado,) = avaliar_regras(ordem_base)
    assert achado.codigo == "RETIRADA_SEM_MOVIMENTACAO"
    assert achado.evidencia["serie"] == ordem_base["equipamentos"][0]["serie_retirada"]


def test_cobranca_sem_aceite_bloqueia(ordem_base):
    ordem_base["cobranca"] = {"cobrado": True, "valor": 80.0}
    (achado,) = avaliar_regras(ordem_base)
    assert achado.codigo == "COBRANCA_SEM_ACEITE" and "R$ 80,00" in achado.mensagem


def test_cobranca_com_aceite_passa(ordem_base):
    ordem_base["cobranca"] = {"cobrado": True, "valor": 80.0}
    ordem_base["comprovante_aceite"] = True
    assert avaliar_regras(ordem_base) == []


def test_equipamento_novo_sem_teste_bloqueia(ordem_base):
    ordem_base["equipamentos"][0]["teste_registrado"] = False
    assert codigos(ordem_base) == {"EQUIPAMENTO_NOVO_SEM_TESTE"}


def test_desinstalacao_que_instala_bloqueia(ordem_base):
    ordem_base["tipo_servico"] = "DESINSTALACAO"
    assert codigos(ordem_base) == {"TIPO_INCOMPATIVEL"}


def test_manutencao_sem_equipamento_bloqueia(ordem_base):
    ordem_base["equipamentos"] = []
    ordem_base["movimentacoes_estoque"] = []
    assert codigos(ordem_base) == {"TIPO_INCOMPATIVEL"}


def test_preventiva_sem_equipamento_passa(ordem_base):
    ordem_base.update(tipo_servico="PREVENTIVA", equipamentos=[], movimentacoes_estoque=[])
    assert avaliar_regras(ordem_base) == []


def test_serie_repetida_bloqueia(ordem_base):
    item = ordem_base["equipamentos"][0]
    item["serie_instalada"] = item["serie_retirada"]
    assert codigos(ordem_base) == {"SERIE_REPETIDA"}


def test_poucas_fotos_e_so_aviso(ordem_base):
    ordem_base["fotos"] = 1
    (achado,) = avaliar_regras(ordem_base)
    assert achado.codigo == "POUCAS_FOTOS" and achado.severidade is Severidade.AVISO


@pytest.mark.parametrize("fim, minutos", [("2026-10-01T09:20:00", 5), ("2026-10-01T18:00:00", 525)])
def test_duracao_atipica_e_so_aviso(ordem_base, fim, minutos):
    ordem_base["atendimento"] = {"inicio": "2026-10-01T09:15:00", "fim": fim}
    (achado,) = avaliar_regras(ordem_base)
    assert achado.codigo == "DURACAO_ATIPICA" and achado.evidencia["minutos"] == minutos
    assert achado.severidade is Severidade.AVISO


def test_todo_achado_tem_evidencia(cada_ordem):
    for achado in avaliar_regras(cada_ordem):
        assert achado.evidencia and achado.mensagem


def test_regras_batem_com_o_gabarito(cada_ordem):
    esperado = carregar_gabarito()[cada_ordem["id"]]
    assert codigos(cada_ordem) == set(esperado["regras"])
