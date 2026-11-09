#!/usr/bin/env python3
"""Falha o build se aparecer dado pessoal ou segredo nos arquivos versionados.

Propositalmente grosseiro: e-mail fora de example.com, telefone com DDD real,
CPF, chave de API e chave privada nunca são conteúdo legítimo aqui, então
qualquer ocorrência é um achado. Os dados fictícios usam DDD 00, que não existe.

    python tools/scan_pii.py [caminho ...]
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PULAR_SUFIXOS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".zip", ".pdf", ".woff", ".woff2"}
PULAR_PARTES = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
DOMINIOS_PERMITIDOS = ("example.com", "example.org", "users.noreply.github.com")

PADROES = {
    "e-mail": re.compile(r"\b[\w.+-]+@([\w-]+(?:\.[\w-]+)+)\b"),
    "telefone": re.compile(r"\(?\b(\d{2})\)?\s?9?\d{4}-\d{4}\b"),
    "cpf": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    "chave Anthropic": re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),
    "token GitHub": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "chave AWS": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "chave privada": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def achados_no_texto(texto: str) -> list[tuple[str, str]]:
    achados = []
    for nome, padrao in PADROES.items():
        for m in padrao.finditer(texto):
            if nome == "e-mail" and m.group(1).lower().endswith(DOMINIOS_PERMITIDOS):
                continue
            if nome == "telefone" and m.group(1) == "00":
                continue
            achados.append((nome, m.group(0)))
    return achados


def arquivos_versionados() -> list[Path]:
    saida = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    return [Path(linha) for linha in saida.splitlines() if linha]


def varrer(caminhos: list[Path]) -> list[tuple[Path, str, str]]:
    resultado = []
    for caminho in caminhos:
        if caminho.suffix.lower() in PULAR_SUFIXOS or not caminho.is_file():
            continue
        if PULAR_PARTES & set(caminho.parts):
            continue
        if caminho.name == ".env" or (caminho.name.startswith(".env.") and caminho.name != ".env.example"):
            resultado.append((caminho, "arquivo de ambiente", caminho.name))
            continue
        texto = caminho.read_text(encoding="utf-8", errors="ignore")
        resultado += [(caminho, nome, trecho) for nome, trecho in achados_no_texto(texto)]
    return resultado


def main(argv: list[str]) -> int:
    alvos = [Path(a) for a in argv] if argv else arquivos_versionados()
    expandidos: list[Path] = []
    for alvo in alvos:
        expandidos += sorted(p for p in alvo.rglob("*") if p.is_file()) if alvo.is_dir() else [alvo]

    achados = varrer(expandidos)
    if achados:
        print("Possível dado pessoal ou segredo:", file=sys.stderr)
        for caminho, nome, trecho in achados:
            print(f"  {caminho}: {nome}: {trecho}", file=sys.stderr)
        return 1
    print(f"Nenhum dado pessoal ou segredo encontrado em {len(expandidos)} arquivo(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
