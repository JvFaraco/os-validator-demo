"""Roda todas as O.S. fictícias contra o gabarito rotulado à mão."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from . import DADOS, __version__
from .catalogo import carregar_catalogo
from .decisao import carregar_ordem, decidir
from .ia.base import Provedor
from .ia.claude import custo_estimado_usd
from .modelos import Caminho

CAMINHOS = [c.value for c in Caminho]


def carregar_gabarito(caminho: Path | None = None) -> dict[str, dict[str, Any]]:
    caminho = caminho or DADOS / "gabarito.yaml"
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))


def _pct(acertos: int, total: int) -> float:
    return round(100 * acertos / total, 1) if total else 0.0


def avaliar(provedor: Provedor, pasta: Path | None = None, gabarito: Path | None = None) -> dict[str, Any]:
    pasta = pasta or DADOS / "ordens"
    esperado_por_os = carregar_gabarito(gabarito)
    catalogo = carregar_catalogo()

    casos = []
    tokens_entrada = tokens_saida = chamadas = 0
    for arquivo in sorted(pasta.glob("os-*.json")):
        ordem = carregar_ordem(arquivo)
        g = esperado_por_os[ordem["id"]]
        d = decidir(ordem, provedor, catalogo)
        if d.ia and d.ia.bruta:
            chamadas += 1
            tokens_entrada += d.ia.bruta.tokens_entrada
            tokens_saida += d.ia.bruta.tokens_saida
        casos.append({
            "id": ordem["id"],
            "decisao_esperada": g["decisao"],
            "decisao_obtida": d.caminho.value,
            "combinacao_esperada": g.get("combinacao"),
            "combinacao_obtida": d.combinacao.id if d.combinacao else None,
            "regras_esperadas": sorted(g.get("regras", [])),
            "regras_obtidas": sorted({a.codigo for a in d.achados}),
            "ia": d.ia.status.value if d.ia else "NAO_CHAMADA",
            "ia_resposta": d.ia.dados if d.ia else None,
            "motivo": d.motivo,
        })

    n = len(casos)
    acerto_decisao = sum(c["decisao_esperada"] == c["decisao_obtida"] for c in casos)
    com_combinacao = [c for c in casos if c["combinacao_esperada"]]
    acerto_classificacao = sum(c["combinacao_esperada"] == c["combinacao_obtida"] for c in com_combinacao)
    acerto_regras = sum(c["regras_esperadas"] == c["regras_obtidas"] for c in casos)
    matriz = {e: {o: 0 for o in CAMINHOS} for e in CAMINHOS}
    for c in casos:
        matriz[c["decisao_esperada"]][c["decisao_obtida"]] += 1

    erros = [
        c for c in casos
        if c["decisao_esperada"] != c["decisao_obtida"]
        or (c["combinacao_esperada"] and c["combinacao_esperada"] != c["combinacao_obtida"])
    ]
    modelo = getattr(provedor, "modelo", None)
    return {
        "provedor": provedor.nome,
        "modelo": modelo,
        "versao": __version__,
        "gerado_em": date.today().isoformat(),
        "total_os": n,
        "metricas": {
            "decisao": {"acertos": acerto_decisao, "total": n, "pct": _pct(acerto_decisao, n)},
            "classificacao": {
                "acertos": acerto_classificacao,
                "total": len(com_combinacao),
                "pct": _pct(acerto_classificacao, len(com_combinacao)),
            },
            "regras": {"acertos": acerto_regras, "total": n, "pct": _pct(acerto_regras, n)},
        },
        "matriz_confusao": matriz,
        "uso": {
            "chamadas_ia": chamadas,
            "tokens_entrada": tokens_entrada,
            "tokens_saida": tokens_saida,
            "custo_estimado_usd": custo_estimado_usd(modelo, tokens_entrada, tokens_saida),
        },
        "erros": [c["id"] for c in erros],
        "casos": casos,
    }


def salvar(relatorio: dict[str, Any], caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return caminho
