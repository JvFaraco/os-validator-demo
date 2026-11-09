"""Contrato da resposta da IA."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from .. import SCHEMAS
from ..modelos import Combinacao

ABSTENCAO = "NENHUMA"


@lru_cache(maxsize=1)
def schema_resposta() -> dict[str, Any]:
    return json.loads((SCHEMAS / "resposta_ia.schema.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def validador_resposta() -> Draft202012Validator:
    return Draft202012Validator(schema_resposta())


def schema_para_api(opcoes: list[Combinacao]) -> dict[str, Any]:
    """Versão do schema enviada ao modelo como saída estruturada.

    `combinacao_id` vira um `enum` com as opções desta O.S. mais NENHUMA, então
    o próprio decodificador do modelo fica preso ao catálogo. Restrições de
    tamanho e padrão ficam só na validação local, que roda de qualquer jeito.
    """
    schema = copy.deepcopy(schema_resposta())
    for chave in ("$schema", "title", "description"):
        schema.pop(chave, None)
    for propriedade in schema["properties"].values():
        propriedade.pop("maxLength", None)
        propriedade.pop("pattern", None)
    schema["properties"]["combinacao_id"]["enum"] = [c.id for c in opcoes] + [ABSTENCAO]
    return schema
