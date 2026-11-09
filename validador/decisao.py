"""Orquestra uma O.S.: contrato → regras → catálogo → guarda → sanitização → IA → decisão.

A decisão é sempre do código. A IA devolve uma classificação e um trecho; ela
nunca diz se a O.S. está aprovada, e nada do que ela escreve muda o caminho
além de "aceita" ou "não aceita".
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from . import SCHEMAS
from .catalogo import Catalogo, carregar_catalogo
from .guarda import trecho_com_instrucao
from .ia.base import ErroDoProvedor, Provedor
from .ia.validacao import validar_resposta
from .modelos import Achado, Caminho, Decisao, ResultadoIA, Severidade, StatusIA
from .regras import avaliar_regras
from .sanitizacao import VazamentoDeDadoPessoal, montar_pacote_ia


@lru_cache(maxsize=1)
def _validador_ordem() -> Draft202012Validator:
    return Draft202012Validator(json.loads((SCHEMAS / "ordem.schema.json").read_text(encoding="utf-8")))


def carregar_ordem(caminho: Path) -> dict[str, Any]:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def nota_ao_tecnico(bloqueios: list[Achado]) -> str:
    itens = "\n".join(f"- {a.mensagem}" for a in bloqueios)
    return f"O.S. devolvida para correção. Ajuste antes de reenviar:\n{itens}"


def decidir(ordem: dict[str, Any], provedor: Provedor, catalogo: Catalogo | None = None) -> Decisao:
    catalogo = catalogo or carregar_catalogo()
    os_id = str(ordem.get("id", "?"))

    erros = sorted(_validador_ordem().iter_errors(ordem), key=lambda e: list(e.path))
    if erros:
        return Decisao(os_id, Caminho.REVISAO, f"O.S. fora do contrato de entrada: {erros[0].message}")

    achados = avaliar_regras(ordem, catalogo)
    bloqueios = [a for a in achados if a.severidade is Severidade.BLOQUEIO]
    avisos = [a.mensagem for a in achados if a.severidade is Severidade.AVISO]

    if bloqueios:
        return Decisao(
            os_id, Caminho.CORRECAO,
            "Pendência verificável pelas regras; a IA não foi chamada.",
            achados=achados,
            nota_ao_tecnico=nota_ao_tecnico(bloqueios),
        )

    opcoes = catalogo.opcoes_para(ordem)
    if not opcoes:
        return Decisao(
            os_id, Caminho.REVISAO,
            "Nenhuma combinação do catálogo para este tipo de serviço e estes equipamentos.",
            achados=achados, avisos_ao_conferente=avisos,
        )

    instrucao = trecho_com_instrucao(ordem.get("nota_tecnico") or "")
    if instrucao:
        return Decisao(
            os_id, Caminho.REVISAO,
            f'A nota contém texto dirigido ao sistema ("{instrucao}"); a IA não foi chamada.',
            achados=achados, opcoes=opcoes, avisos_ao_conferente=avisos,
        )

    try:
        pacote = montar_pacote_ia(ordem)
    except VazamentoDeDadoPessoal as erro:
        return Decisao(
            os_id, Caminho.REVISAO,
            f"Pacote da IA barrado por dado pessoal ({erro}); a IA não foi chamada.",
            achados=achados, opcoes=opcoes, avisos_ao_conferente=avisos,
        )

    try:
        bruta = provedor.classificar(pacote.dados, opcoes)
    except ErroDoProvedor as erro:
        ia = ResultadoIA(StatusIA.ERRO, f"Provedor de IA indisponível: {erro}")
    else:
        ia = validar_resposta(bruta, opcoes, pacote.dados["nota_tecnico"])

    if ia.status is not StatusIA.ACEITA:
        return Decisao(
            os_id, Caminho.REVISAO, ia.motivo,
            achados=achados, pacote=pacote, opcoes=opcoes, ia=ia, avisos_ao_conferente=avisos,
        )

    observacao = (ia.dados or {}).get("observacao_conferente", "").strip()
    if observacao:
        avisos = [*avisos, f"Leitura da IA: {observacao}"]
    return Decisao(
        os_id, Caminho.PRONTA,
        "Sem pendência nas regras e classificação aceita.",
        achados=achados, pacote=pacote, opcoes=opcoes, ia=ia,
        combinacao=ia.combinacao, avisos_ao_conferente=avisos,
    )
