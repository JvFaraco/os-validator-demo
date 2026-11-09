"""Catálogo fechado de combinações problema → solução."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from . import CONFIG
from .modelos import Combinacao

CAMPOS_OBRIGATORIOS = ("id", "equipamento", "problema", "solucao", "tipos")


class CatalogoInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Catalogo:
    versao: int
    tipos_de_servico: tuple[str, ...]
    equipamentos: dict[str, str]
    combinacoes: dict[str, Combinacao]

    def nome_equipamento(self, categoria: str) -> str:
        return self.equipamentos.get(categoria, categoria.lower().replace("_", " "))

    def opcoes_para(self, ordem: dict[str, Any]) -> list[Combinacao]:
        """Combinações que fazem sentido para esta O.S.

        Filtra pelo tipo de serviço e, na manutenção, pelos equipamentos em que
        houve ação. É o Python quem estreita as opções; a IA só escolhe entre
        o que sobrou.
        """
        tipo = ordem["tipo_servico"]
        candidatas = [c for c in self.combinacoes.values() if tipo in c.tipos]
        if tipo == "MANUTENCAO":
            categorias = {e["categoria"] for e in ordem.get("equipamentos", [])}
            candidatas = [c for c in candidatas if c.equipamento in categorias]
        return candidatas


def _validar(bruto: dict[str, Any]) -> Catalogo:
    tipos = tuple(bruto.get("tipos_de_servico", ()))
    equipamentos = dict(bruto.get("equipamentos", {}))
    combinacoes: dict[str, Combinacao] = {}
    for item in bruto.get("combinacoes", []):
        faltando = [c for c in CAMPOS_OBRIGATORIOS if not item.get(c)]
        if faltando:
            raise CatalogoInvalido(f"combinação {item.get('id')!r} sem {faltando}")
        if item["id"] in combinacoes:
            raise CatalogoInvalido(f"id repetido: {item['id']}")
        if item["equipamento"] not in equipamentos:
            raise CatalogoInvalido(f"{item['id']}: equipamento desconhecido {item['equipamento']}")
        desconhecidos = set(item["tipos"]) - set(tipos)
        if desconhecidos:
            raise CatalogoInvalido(f"{item['id']}: tipos desconhecidos {sorted(desconhecidos)}")
        combinacoes[item["id"]] = Combinacao(
            id=item["id"],
            equipamento=item["equipamento"],
            problema=item["problema"],
            solucao=item["solucao"],
            tipos=tuple(item["tipos"]),
            palavras_chave=tuple(item.get("palavras_chave", ())),
        )
    if not combinacoes:
        raise CatalogoInvalido("catálogo vazio")
    return Catalogo(int(bruto.get("versao", 0)), tipos, equipamentos, combinacoes)


def carregar_catalogo(caminho: Path | None = None) -> Catalogo:
    caminho = caminho or CONFIG / "catalogo.yaml"
    if caminho == CONFIG / "catalogo.yaml":
        return _catalogo_padrao()
    return _validar(yaml.safe_load(caminho.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _catalogo_padrao() -> Catalogo:
    return _validar(yaml.safe_load((CONFIG / "catalogo.yaml").read_text(encoding="utf-8")))
