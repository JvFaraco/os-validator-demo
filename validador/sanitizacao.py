"""O que pode sair da máquina para o modelo.

Duas camadas, de propósito:

1. **Allowlist de campos.** O pacote da IA é montado do zero com três campos
   (tipo de serviço, categoria e ação de cada equipamento, nota do técnico).
   Nome, telefone, endereço, matrícula, séries e valores nunca são copiados.
   O resultado é validado contra `schemas/pacote_ia.schema.json`, com
   `additionalProperties: false` em todos os níveis.
2. **Máscara no texto livre.** A nota é escrita por gente e pode trazer
   telefone, e-mail ou o nome do cliente. Padrões conhecidos são mascarados,
   e os valores pessoais da própria O.S. são procurados e trocados na nota.

Por fim, `garantir_sem_dado_pessoal` confere o pacote pronto contra os dados
pessoais da O.S. Se algo escapou, a O.S. vai para revisão humana sem chamar a IA.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from . import SCHEMAS
from .modelos import PacoteIA

CAMPOS_PERMITIDOS = ("tipo_servico", "equipamentos[].categoria", "equipamentos[].acao", "nota_tecnico")

PADROES = (
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("CPF", re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")),
    ("TELEFONE", re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b")),
    ("CEP", re.compile(r"\b\d{5}-\d{3}\b")),
)
TAMANHO_MINIMO_TOKEN_NOME = 3


class VazamentoDeDadoPessoal(RuntimeError):
    """O pacote pronto ainda contém um dado pessoal da O.S."""


@lru_cache(maxsize=1)
def _validador_pacote() -> Draft202012Validator:
    schema = json.loads((SCHEMAS / "pacote_ia.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def _pessoas(ordem: dict[str, Any]) -> list[dict[str, Any]]:
    return [p for p in (ordem.get("cliente"), ordem.get("tecnico")) if isinstance(p, dict)]


def _tokens_de_nome(nome: str) -> list[str]:
    return [t for t in re.findall(r"\w+", nome) if len(t) >= TAMANHO_MINIMO_TOKEN_NOME]


def _logradouro(endereco: str) -> str:
    return re.split(r"\s+-\s+|,", endereco, maxsplit=1)[0].strip()


def mascarar_texto(texto: str, ordem: dict[str, Any]) -> tuple[str, dict[str, int]]:
    """Troca dado pessoal por marcadores como [TELEFONE] e [NOME]."""
    contagem: dict[str, int] = {}

    def trocar(padrao: re.Pattern[str], marcador: str, alvo: str) -> str:
        novo, n = padrao.subn(f"[{marcador}]", alvo)
        if n:
            contagem[marcador] = contagem.get(marcador, 0) + n
        return novo

    for marcador, padrao in PADROES:
        texto = trocar(padrao, marcador, texto)

    for pessoa in _pessoas(ordem):
        endereco = pessoa.get("endereco") or ""
        for trecho in filter(None, (endereco, _logradouro(endereco))):
            texto = trocar(re.compile(re.escape(trecho), re.IGNORECASE), "ENDERECO", texto)
        nome = pessoa.get("nome") or ""
        if nome:
            texto = trocar(re.compile(rf"\b{re.escape(nome)}\b", re.IGNORECASE), "NOME", texto)
            for token in _tokens_de_nome(nome):
                texto = trocar(re.compile(rf"\b{re.escape(token)}\b", re.IGNORECASE), "NOME", texto)
    return texto, contagem


def _caminhos(valor: Any, prefixo: str = "") -> set[str]:
    if isinstance(valor, dict):
        caminhos: set[str] = set()
        for chave, filho in valor.items():
            atual = f"{prefixo}.{chave}" if prefixo else chave
            caminhos |= _caminhos(filho, atual) or {atual}
        return caminhos
    if isinstance(valor, list):
        caminhos = set()
        for item in valor:
            caminhos |= _caminhos(item, f"{prefixo}[]")
        return caminhos
    return set()


def montar_pacote_ia(ordem: dict[str, Any]) -> PacoteIA:
    nota, mascaras = mascarar_texto(ordem.get("nota_tecnico") or "", ordem)
    dados = {
        "tipo_servico": ordem["tipo_servico"],
        "equipamentos": [
            {"categoria": e["categoria"], "acao": e["acao"]} for e in ordem.get("equipamentos", [])
        ],
        "nota_tecnico": nota,
    }
    erros = sorted(_validador_pacote().iter_errors(dados), key=lambda e: e.path)
    if erros:
        raise VazamentoDeDadoPessoal(f"pacote fora do contrato: {erros[0].message}")
    garantir_sem_dado_pessoal(dados, ordem)
    removidos = sorted(_caminhos(ordem) - set(CAMPOS_PERMITIDOS))
    return PacoteIA(dados=dados, removidos=removidos, mascaras=mascaras)


def garantir_sem_dado_pessoal(dados: dict[str, Any], ordem: dict[str, Any]) -> None:
    """Falha se qualquer dado pessoal da O.S. aparecer no pacote serializado."""
    texto = json.dumps(dados, ensure_ascii=False)
    digitos = re.sub(r"\D", "", texto)
    for pessoa in _pessoas(ordem):
        for token in _tokens_de_nome(pessoa.get("nome") or ""):
            if re.search(rf"\b{re.escape(token)}\b", texto, re.IGNORECASE):
                raise VazamentoDeDadoPessoal("nome")
        telefone = re.sub(r"\D", "", pessoa.get("telefone") or "")
        if len(telefone) >= 8 and telefone[-8:] in digitos:
            raise VazamentoDeDadoPessoal("telefone")
        logradouro = _logradouro(pessoa.get("endereco") or "")
        if logradouro and logradouro.casefold() in texto.casefold():
            raise VazamentoDeDadoPessoal("endereco")
    for marcador, padrao in PADROES:
        if padrao.search(texto):
            raise VazamentoDeDadoPessoal(marcador.lower())
