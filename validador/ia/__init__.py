"""Camada de IA: interface de provedor, contrato de saída e validação."""

from .base import ErroDoProvedor, Provedor, obter_provedor

__all__ = ["ErroDoProvedor", "Provedor", "obter_provedor"]
