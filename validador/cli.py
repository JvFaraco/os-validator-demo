"""Linha de comando.

    python -m validador analisar data/ordens/os-0007.json
    python -m validador avaliar
    python -m validador avaliar --provedor anthropic --modelo claude-haiku-5-5 --salvar
    python -m validador avaliar --de resultados/avaliacao-anthropic-claude-haiku-5-5.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import RESULTADOS
from .avaliacao import avaliar, salvar
from .decisao import carregar_ordem, decidir
from .ia.base import PROVEDORES, ErroDoProvedor, obter_provedor
from .ia.claude import MODELO_PADRAO
from .saida import formatar_analise, formatar_avaliacao, usar_cor


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m validador", description=__doc__.splitlines()[0])
    comum = argparse.ArgumentParser(add_help=False)
    comum.add_argument("--provedor", choices=PROVEDORES, default="falso",
                       help="falso (padrão, offline) ou anthropic (exige ANTHROPIC_API_KEY)")
    comum.add_argument("--modelo", default=None,
                       help=f"modelo do provedor anthropic (padrão: {MODELO_PADRAO})")
    cor = comum.add_mutually_exclusive_group()
    cor.add_argument("--cor", dest="cor", action="store_true", default=None, help="força cores ANSI")
    cor.add_argument("--sem-cor", dest="cor", action="store_false", help="desliga cores ANSI")

    sub = p.add_subparsers(dest="comando", required=True)
    a = sub.add_parser("analisar", parents=[comum], help="mostra o caminho completo de uma O.S.")
    a.add_argument("arquivo", type=Path)
    v = sub.add_parser("avaliar", parents=[comum], help="roda todas as O.S. contra o gabarito")
    v.add_argument("--salvar", nargs="?", const="", default=None, metavar="ARQUIVO",
                   help="grava o relatório em JSON (padrão: resultados/avaliacao-<provedor>[-<modelo>].json)")
    v.add_argument("--de", type=Path, default=None, metavar="ARQUIVO",
                   help="só exibe um relatório já salvo (ex.: a rodada real versionada), sem chamar provedor")
    return p


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    cor = usar_cor(args.cor)

    if args.comando == "avaliar" and args.de:
        print(formatar_avaliacao(json.loads(args.de.read_text(encoding="utf-8")), cor))
        return 0

    if args.modelo and args.provedor != "anthropic":
        print("--modelo só vale com --provedor anthropic.", file=sys.stderr)
        return 2
    try:
        provedor = obter_provedor(args.provedor, args.modelo)
    except ErroDoProvedor as erro:
        print(f"Provedor indisponível: {erro}", file=sys.stderr)
        return 2

    if args.comando == "analisar":
        ordem = carregar_ordem(args.arquivo)
        print(formatar_analise(ordem, decidir(ordem, provedor), provedor.nome, cor))
        return 0

    relatorio = avaliar(provedor)
    print(formatar_avaliacao(relatorio, cor))
    if args.salvar is not None:
        if args.salvar:
            destino = Path(args.salvar)
        else:
            sufixo = f"-{provedor.modelo}" if getattr(provedor, "modelo", None) else ""
            destino = RESULTADOS / f"avaliacao-{provedor.nome}{sufixo}.json"
        print(f"\nRelatório salvo em {salvar(relatorio, destino)}")
    return 0
