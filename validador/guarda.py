"""Detecção determinística de texto dirigido ao sistema dentro da nota.

A nota é escrita por pessoas e vai para o modelo. Frases de comando óbvias
("ignore as regras", "aprove", "classifique como") levam a O.S. para revisão
humana antes de qualquer chamada à IA, qualquer que seja o provedor.

Detecção por padrão não pega tudo. Por isso há outras camadas: o modelo é
instruído a se abster diante disso, precisa citar um trecho real da nota e
não tem como decidir o caminho da O.S.
"""

from __future__ import annotations

import re
import unicodedata

PADRAO_INSTRUCAO = re.compile(
    r"\b("
    r"ignore (as |todas as )?(regras|instrucoes)"
    r"|desconsidere (as |todas as )?(regras|instrucoes)"
    r"|classifique como"
    r"|responda que"
    r"|aprove"
    r")\b"
)


def sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def trecho_com_instrucao(nota: str) -> str | None:
    m = PADRAO_INSTRUCAO.search(sem_acento(nota))
    return m.group(0) if m else None
