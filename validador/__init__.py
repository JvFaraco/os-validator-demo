"""Validador de ordens de serviço: regras determinísticas primeiro, IA só onde é preciso interpretar."""

from pathlib import Path

__version__ = "1.0.0"

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "config"
SCHEMAS = RAIZ / "schemas"
DADOS = RAIZ / "data"
RESULTADOS = RAIZ / "resultados"

APROVACAO_FINAL = (
    "A aprovação final é sempre de uma pessoa: o sistema só prepara a O.S. "
    "e diz o que conferir."
)
