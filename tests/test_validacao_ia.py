"""A resposta da IA só vale se passar por todas as conferências."""

from __future__ import annotations

import json

import pytest

from validador.catalogo import carregar_catalogo
from validador.ia.schema import schema_para_api
from validador.ia.validacao import trecho_esta_na_nota, validar_resposta
from validador.modelos import RespostaBruta, StatusIA

CAT = carregar_catalogo()
OPCOES = [CAT.combinacoes["C12"], CAT.combinacoes["C13"], CAT.combinacoes["C14"]]
NOTA = "Câmera sem imagem. Reconfigurei a rede da câmera. [NOME] pediu retorno pelo [TELEFONE]."


def resposta(**campos) -> RespostaBruta:
    dados = {
        "combinacao_id": "C13",
        "confianca": "alta",
        "trecho_citado": "Reconfigurei a rede da câmera",
        "observacao_conferente": "Problema de rede, não de hardware.",
    }
    dados.update(campos)
    return RespostaBruta(texto=json.dumps(dados, ensure_ascii=False), provedor="teste")


def test_resposta_correta_e_aceita():
    r = validar_resposta(resposta(), OPCOES, NOTA)
    assert r.status is StatusIA.ACEITA and r.combinacao.id == "C13"
    assert all(ok for _, ok in r.verificacoes)


def test_json_invalido_e_rejeitado():
    r = validar_resposta(RespostaBruta("isto não é json", "teste"), OPCOES, NOTA)
    assert r.status is StatusIA.REJEITADA and "JSON" in r.motivo


@pytest.mark.parametrize("mexer", [
    {"decisao": "PRONTA_PARA_VALIDACAO"},  # campo a mais: a IA não decide
    {"confianca": "altissima"},
    {"combinacao_id": "C13; DROP"},
    {"observacao_conferente": "x" * 401},
])
def test_fora_do_schema_e_rejeitado(mexer):
    r = validar_resposta(resposta(**mexer), OPCOES, NOTA)
    assert r.status is StatusIA.REJEITADA and "schema" in r.motivo


def test_resposta_sem_campo_obrigatorio_e_rejeitada():
    dados = json.loads(resposta().texto)
    del dados["trecho_citado"]
    r = validar_resposta(RespostaBruta(json.dumps(dados), "teste"), OPCOES, NOTA)
    assert r.status is StatusIA.REJEITADA


def test_combinacao_do_catalogo_mas_fora_das_opcoes_desta_os_e_rejeitada():
    # C01 existe no catálogo, mas é de sensor de movimento; esta O.S. é de câmera.
    r = validar_resposta(resposta(combinacao_id="C01"), OPCOES, NOTA)
    assert r.status is StatusIA.REJEITADA and "fora das opções" in r.motivo


def test_combinacao_inexistente_e_rejeitada():
    r = validar_resposta(resposta(combinacao_id="C99"), OPCOES, NOTA)
    assert r.status is StatusIA.REJEITADA


def test_trecho_inventado_e_rejeitado():
    r = validar_resposta(resposta(trecho_citado="Troquei a câmera por uma nova"), OPCOES, NOTA)
    assert r.status is StatusIA.REJEITADA and "trecho" in r.motivo


def test_trecho_com_marcador_e_conferido_contra_a_nota_mascarada():
    """A IA viu [TELEFONE]; citar o trecho como ela viu tem que passar."""
    r = validar_resposta(resposta(trecho_citado="[NOME] pediu retorno pelo [TELEFONE]"), OPCOES, NOTA)
    assert r.status is StatusIA.ACEITA


def test_trecho_tolera_maiusculas_espacos_e_aspas():
    assert trecho_esta_na_nota('"reconfigurei   a REDE da câmera."', NOTA)


def test_trecho_curto_demais_nao_vale():
    assert not trecho_esta_na_nota("rede", NOTA)


def test_confianca_baixa_fica_abaixo_do_limiar():
    r = validar_resposta(resposta(confianca="baixa"), OPCOES, NOTA)
    assert r.status is StatusIA.REJEITADA and "limiar" in r.motivo


def test_abstencao_e_registrada_como_abstencao():
    r = validar_resposta(resposta(combinacao_id="NENHUMA", confianca="baixa"), OPCOES, NOTA)
    assert r.status is StatusIA.ABSTENCAO


def test_schema_da_api_prende_a_escolha_as_opcoes():
    schema = schema_para_api(OPCOES)
    assert schema["properties"]["combinacao_id"]["enum"] == ["C12", "C13", "C14", "NENHUMA"]
    assert schema["additionalProperties"] is False
    assert "maxLength" not in json.dumps(schema)
