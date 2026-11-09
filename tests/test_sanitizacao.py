"""Dado pessoal nunca vai para a IA."""

from __future__ import annotations

import json
import re

import pytest

from validador.sanitizacao import (
    VazamentoDeDadoPessoal,
    garantir_sem_dado_pessoal,
    mascarar_texto,
    montar_pacote_ia,
)

from .conftest import carregar


def _valores_pessoais(ordem: dict) -> list[str]:
    valores = []
    for pessoa in (ordem["cliente"], ordem["tecnico"]):
        valores += [t for t in re.findall(r"\w+", pessoa["nome"]) if len(t) >= 3]
    valores.append(re.sub(r"\D", "", ordem["cliente"]["telefone"])[-8:])
    valores.append(ordem["cliente"]["endereco"].split(",")[0])
    valores.append(ordem["tecnico"]["matricula"])
    return valores


def test_pacote_so_tem_campos_da_allowlist(cada_ordem):
    pacote = montar_pacote_ia(cada_ordem).dados
    assert set(pacote) == {"tipo_servico", "equipamentos", "nota_tecnico"}
    for equipamento in pacote["equipamentos"]:
        assert set(equipamento) == {"categoria", "acao"}


def test_nenhum_dado_pessoal_de_nenhuma_os_chega_a_ia(cada_ordem):
    serializado = json.dumps(montar_pacote_ia(cada_ordem).dados, ensure_ascii=False)
    so_digitos = re.sub(r"\D", "", serializado)
    for valor in _valores_pessoais(cada_ordem):
        if valor.isdigit():
            assert valor not in so_digitos
        else:
            assert not re.search(rf"\b{re.escape(valor)}\b", serializado, re.IGNORECASE), valor


def test_series_e_valores_ficam_na_maquina(cada_ordem):
    serializado = json.dumps(montar_pacote_ia(cada_ordem).dados)
    for equipamento in cada_ordem["equipamentos"]:
        for chave in ("serie", "serie_retirada", "serie_instalada"):
            if equipamento.get(chave):
                assert equipamento[chave] not in serializado


def test_nome_e_telefone_na_nota_sao_mascarados():
    ordem = carregar("os-0007.json")
    pacote = montar_pacote_ia(ordem)
    nota = pacote.dados["nota_tecnico"]
    assert "Gabriela" not in nota and "98888" not in nota
    assert "[NOME]" in nota and "[TELEFONE]" in nota
    assert pacote.mascaras == {"NOME": 1, "TELEFONE": 1}


def test_email_na_nota_e_mascarado():
    nota = montar_pacote_ia(carregar("os-0012.json")).dados["nota_tecnico"]
    assert "@" not in nota and "[EMAIL]" in nota


def test_cpf_e_cep_no_texto_sao_mascarados(ordem_base):
    cpf = "123.456.789" + "-09"
    texto, contagem = mascarar_texto(f"CPF {cpf}, CEP 88000-000.", ordem_base)
    assert cpf not in texto and "88000" not in texto
    assert contagem == {"CPF": 1, "CEP": 1}


def test_endereco_citado_na_nota_e_mascarado(ordem_base):
    ordem_base["nota_tecnico"] = f"Cheguei na {ordem_base['cliente']['endereco']} às 9h e troquei o sensor."
    nota = montar_pacote_ia(ordem_base).dados["nota_tecnico"]
    assert "Rua Exemplo" not in nota and "[ENDERECO]" in nota


def test_campos_pessoais_aparecem_como_removidos():
    removidos = montar_pacote_ia(carregar("os-0007.json")).removidos
    for campo in ("cliente.nome", "cliente.telefone", "cliente.endereco", "tecnico.nome", "tecnico.matricula"):
        assert campo in removidos


def test_guarda_final_barra_vazamento(ordem_base):
    pacote = montar_pacote_ia(ordem_base).dados
    pacote["nota_tecnico"] += f" Falar com {ordem_base['cliente']['nome']}."
    with pytest.raises(VazamentoDeDadoPessoal):
        garantir_sem_dado_pessoal(pacote, ordem_base)


def test_guarda_final_barra_telefone_sem_formatacao(ordem_base):
    pacote = montar_pacote_ia(ordem_base).dados
    digitos = "".join(c for c in ordem_base["cliente"]["telefone"] if c.isdigit())
    pacote["nota_tecnico"] += f" contato {digitos}"
    with pytest.raises(VazamentoDeDadoPessoal):
        garantir_sem_dado_pessoal(pacote, ordem_base)
