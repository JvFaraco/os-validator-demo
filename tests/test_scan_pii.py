"""O scanner pega o que deve e deixa passar os fictícios.

Os valores "reais" são montados em tempo de execução para o próprio arquivo de
teste não disparar o scanner no CI.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scan_pii", RAIZ / "tools" / "scan_pii.py")
scan_pii = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan_pii)


def tipos(texto: str) -> set[str]:
    return {nome for nome, _ in scan_pii.achados_no_texto(texto)}


def test_telefone_com_ddd_real_e_achado():
    assert tipos("ligar no (4" + "8) 99123-4567") == {"telefone"}


def test_telefone_ficticio_ddd_00_passa():
    assert tipos("ligar no (00) 98888-1234") == set()


def test_email_real_e_achado_e_example_passa():
    assert tipos("fulano@" + "empresa.com.br") == {"e-mail"}
    assert tipos("lucas.exemplo@example.com") == set()


def test_cpf_e_chaves_sao_achados():
    assert "cpf" in tipos("123.456.789" + "-09")
    assert "chave Anthropic" in tipos("sk-ant-" + "a" * 24)
    assert "token GitHub" in tipos("ghp_" + "b" * 36)


def test_dados_do_repositorio_estao_limpos():
    alvos = [RAIZ / "data", RAIZ / "config", RAIZ / "validador", RAIZ / "tests"]
    arquivos = [p for alvo in alvos for p in alvo.rglob("*") if p.is_file()]
    assert scan_pii.varrer(arquivos) == []
