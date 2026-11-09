"""Provedor falso: determinístico, offline, sem custo.

É a linha de base e o padrão dos testes e do CI. Casa prefixos de palavra
(`palavras_chave` do catálogo) com a nota já mascarada e se abstém quando não
acha nada ou quando há empate. Não entende negação, contexto nem contradição:
é justamente isso que a comparação com um modelo de verdade deve mostrar.

Ele devolve JSON no mesmo contrato do provedor real e passa pela mesma
validação; nada no fluxo sabe qual provedor respondeu.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..guarda import sem_acento as _sem_acento
from ..modelos import Combinacao, RespostaBruta
from .schema import ABSTENCAO


def _frases(nota: str) -> list[str]:
    return [f.strip() for f in re.split(r"(?<=[.;!?])\s+", nota) if f.strip()]


class ProvedorFalso:
    nome = "falso"
    modelo = None

    def classificar(self, pacote: dict[str, Any], opcoes: list[Combinacao]) -> RespostaBruta:
        nota = pacote["nota_tecnico"]
        normalizada = _sem_acento(nota)
        frases = _frases(nota)

        pontos: dict[str, list[str]] = {}
        for opcao in opcoes:
            achadas = [p for p in opcao.palavras_chave if re.search(rf"\b{p}", normalizada)]
            if achadas:
                pontos[opcao.id] = achadas

        if not pontos:
            return self._responder(
                ABSTENCAO, "baixa", frases[0] if frases else "",
                "Nenhuma palavra-chave do catálogo encontrada na nota.",
            )

        melhor = max(len(v) for v in pontos.values())
        empatadas = [k for k, v in pontos.items() if len(v) == melhor]
        if len(empatadas) > 1:
            return self._responder(
                ABSTENCAO, "baixa", frases[0],
                f"Empate entre {', '.join(empatadas)} por palavras-chave.",
            )

        escolha = empatadas[0]
        primeira = re.compile(rf"\b{pontos[escolha][0]}")
        trecho = self._frase_com(frases, primeira) or frases[0]
        return self._responder(
            escolha, "alta" if melhor >= 2 else "media", trecho,
            f"Escolha por palavras-chave: {', '.join(pontos[escolha])}.",
        )

    @staticmethod
    def _frase_com(frases: list[str], padrao: re.Pattern[str]) -> str | None:
        return next((f for f in frases if padrao.search(_sem_acento(f))), None)

    def _responder(self, combinacao: str, confianca: str, trecho: str, observacao: str) -> RespostaBruta:
        texto = json.dumps(
            {
                "combinacao_id": combinacao,
                "confianca": confianca,
                "trecho_citado": trecho[:300],
                "observacao_conferente": observacao,
            },
            ensure_ascii=False,
        )
        return RespostaBruta(texto=texto, provedor=self.nome)
