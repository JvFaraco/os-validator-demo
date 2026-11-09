from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from validador import DADOS

ORDENS = sorted((DADOS / "ordens").glob("os-*.json"))


def carregar(nome: str) -> dict:
    return json.loads((DADOS / "ordens" / nome).read_text(encoding="utf-8"))


@pytest.fixture
def ordem_base() -> dict:
    """Uma O.S. sem nenhuma pendência (OS-0001), copiada para cada teste mexer à vontade."""
    return copy.deepcopy(carregar("os-0001.json"))


@pytest.fixture(params=ORDENS, ids=lambda p: Path(p).stem)
def cada_ordem(request) -> dict:
    return json.loads(Path(request.param).read_text(encoding="utf-8"))
