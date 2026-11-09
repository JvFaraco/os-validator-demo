"""Provedor real: API da Anthropic com saída estruturada.

Só é usado com `--provedor anthropic` e `ANTHROPIC_API_KEY` definida. O modelo
padrão é o Haiku: classificar uma nota curta numa lista fechada não pede o
modelo mais caro, e o `--modelo` deixa comparar com Sonnet ou Opus.

A resposta é presa ao schema por `output_config.format` (com o `enum` das
opções desta O.S.) e, mesmo assim, validada de novo localmente: o contrato
vale para qualquer provedor, e a conferência do trecho citado só pode ser
feita aqui.
"""

from __future__ import annotations

import os
from typing import Any

from ..modelos import Combinacao, RespostaBruta
from .base import ErroDoProvedor
from .prompt import INSTRUCOES, montar_mensagem
from .schema import schema_para_api

try:  # o SDK é um extra opcional: pip install -e ".[ia]"
    import anthropic
except ImportError:  # pragma: no cover - depende do ambiente
    anthropic = None

MODELO_PADRAO = "claude-haiku-5-5"
ESFORCO_PADRAO = "low"   # classificação curta: pouco raciocínio, menos tokens
MAX_TOKENS = 4096        # inclui o raciocínio interno; a resposta em si tem ~100 tokens

# US$ por milhão de tokens (entrada, saída). Referência de nov/2026, só para a
# estimativa impressa na avaliação; confira a página de preços antes de citar.
PRECOS_USD_POR_MILHAO = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


def custo_estimado_usd(modelo: str | None, tokens_entrada: int, tokens_saida: int) -> float | None:
    precos = PRECOS_USD_POR_MILHAO.get(modelo or "")
    if not precos:
        return None
    return (tokens_entrada * precos[0] + tokens_saida * precos[1]) / 1_000_000


def _erros_da_api() -> tuple[type[BaseException], ...]:
    if anthropic is None:
        return ()
    return (anthropic.APIConnectionError, anthropic.APIStatusError)


class ProvedorClaude:
    nome = "anthropic"

    def __init__(self, modelo: str = MODELO_PADRAO, cliente: Any = None, esforco: str = ESFORCO_PADRAO):
        if cliente is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise ErroDoProvedor(
                    "ANTHROPIC_API_KEY não definida. Sem ela, use o provedor padrão (--provedor falso)."
                )
            if anthropic is None:
                raise ErroDoProvedor('SDK da Anthropic não instalado: pip install -e ".[ia]"')
            cliente = anthropic.Anthropic(max_retries=3)
        self.cliente = cliente
        self.modelo = modelo
        self.esforco = esforco

    def classificar(self, pacote: dict[str, Any], opcoes: list[Combinacao]) -> RespostaBruta:
        try:
            resposta = self.cliente.messages.create(
                model=self.modelo,
                max_tokens=MAX_TOKENS,
                system=INSTRUCOES,
                messages=[{"role": "user", "content": montar_mensagem(pacote, opcoes)}],
                output_config={
                    "effort": self.esforco,
                    "format": {"type": "json_schema", "schema": schema_para_api(opcoes)},
                },
            )
        except _erros_da_api() as erro:
            raise ErroDoProvedor(f"{type(erro).__name__}: {erro}") from erro

        if resposta.stop_reason == "refusal":
            raise ErroDoProvedor("o modelo recusou a solicitação")
        if resposta.stop_reason == "max_tokens":
            raise ErroDoProvedor("resposta cortada por max_tokens")

        texto = next((b.text for b in resposta.content if b.type == "text"), "")
        uso = resposta.usage
        return RespostaBruta(
            texto=texto,
            provedor=self.nome,
            modelo=self.modelo,
            tokens_entrada=getattr(uso, "input_tokens", 0) or 0,
            tokens_saida=getattr(uso, "output_tokens", 0) or 0,
        )
