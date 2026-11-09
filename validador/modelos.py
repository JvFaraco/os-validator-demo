"""Tipos compartilhados entre as etapas do fluxo."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severidade(StrEnum):
    BLOQUEIO = "BLOQUEIO"  # volta ao técnico
    AVISO = "AVISO"        # segue ao conferente, escrito na O.S.


class Caminho(StrEnum):
    PRONTA = "PRONTA_PARA_VALIDACAO"
    CORRECAO = "PRECISA_CORRECAO"
    REVISAO = "REVISAO_HUMANA"


class StatusIA(StrEnum):
    ACEITA = "ACEITA"
    ABSTENCAO = "ABSTENCAO"      # o modelo respondeu NENHUMA
    REJEITADA = "REJEITADA"      # resposta fora do schema, do catálogo ou sem lastro na nota
    ERRO = "ERRO"                # provedor indisponível, recusa, corte


@dataclass(frozen=True)
class Achado:
    codigo: str
    severidade: Severidade
    mensagem: str
    evidencia: dict[str, Any]


@dataclass(frozen=True)
class Combinacao:
    id: str
    equipamento: str
    problema: str
    solucao: str
    tipos: tuple[str, ...]
    palavras_chave: tuple[str, ...] = ()

    @property
    def rotulo(self) -> str:
        return f"{self.problema} → {self.solucao}"


@dataclass
class RespostaBruta:
    """O que o provedor devolveu, antes de qualquer validação."""

    texto: str
    provedor: str
    modelo: str | None = None
    tokens_entrada: int = 0
    tokens_saida: int = 0


@dataclass
class ResultadoIA:
    status: StatusIA
    motivo: str
    combinacao: Combinacao | None = None
    dados: dict[str, Any] | None = None
    bruta: RespostaBruta | None = None
    verificacoes: list[tuple[str, bool]] = field(default_factory=list)


@dataclass
class PacoteIA:
    """Recorte que sai da máquina, mais o registro do que foi tirado."""

    dados: dict[str, Any]
    removidos: list[str]
    mascaras: dict[str, int]


@dataclass
class Decisao:
    os_id: str
    caminho: Caminho
    motivo: str
    achados: list[Achado] = field(default_factory=list)
    pacote: PacoteIA | None = None
    opcoes: list[Combinacao] = field(default_factory=list)
    ia: ResultadoIA | None = None
    combinacao: Combinacao | None = None
    nota_ao_tecnico: str | None = None
    avisos_ao_conferente: list[str] = field(default_factory=list)
