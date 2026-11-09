"""Interface comum dos provedores de IA."""

from __future__ import annotations

from typing import Any, Protocol

from ..modelos import Combinacao, RespostaBruta

PROVEDORES = ("falso", "anthropic")


class ErroDoProvedor(RuntimeError):
    """Provedor indisponível, sem credencial, recusou ou cortou a resposta."""


class Provedor(Protocol):
    nome: str
    modelo: str | None

    def classificar(self, pacote: dict[str, Any], opcoes: list[Combinacao]) -> RespostaBruta:
        """Recebe o pacote sanitizado e as opções permitidas; devolve o texto cru da resposta."""
        ...


def obter_provedor(nome: str = "falso", modelo: str | None = None) -> Provedor:
    if nome == "falso":
        from .falso import ProvedorFalso

        return ProvedorFalso()
    if nome == "anthropic":
        from .claude import ProvedorClaude

        return ProvedorClaude(modelo=modelo) if modelo else ProvedorClaude()
    raise ValueError(f"provedor desconhecido: {nome!r} (opções: {', '.join(PROVEDORES)})")
