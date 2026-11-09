"""Tudo que a resposta da IA precisa passar antes de valer alguma coisa.

A ordem importa e cada etapa é registrada para a CLI mostrar:

1. JSON válido;
2. dentro do schema (`additionalProperties: false`, enum de confiança, tamanhos);
3. abstenção explícita (NENHUMA) vira revisão humana, sem ser erro;
4. combinação entre as opções permitidas para ESTA O.S. (não basta existir no catálogo);
5. trecho citado presente na nota que a IA recebeu (a nota já mascarada);
6. confiança acima do limiar.
"""

from __future__ import annotations

import json
import unicodedata

from ..modelos import Combinacao, RespostaBruta, ResultadoIA, StatusIA
from .schema import ABSTENCAO, validador_resposta

CONFIANCAS_ACEITAS = {"alta", "media"}
TAMANHO_MINIMO_TRECHO = 8


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto).casefold()
    return " ".join(texto.split()).strip(" \"'“”‘’.,;:")


def trecho_esta_na_nota(trecho: str, nota_mascarada: str) -> bool:
    alvo = normalizar(trecho)
    return len(alvo) >= TAMANHO_MINIMO_TRECHO and alvo in normalizar(nota_mascarada)


def validar_resposta(
    bruta: RespostaBruta, opcoes: list[Combinacao], nota_mascarada: str
) -> ResultadoIA:
    verificacoes: list[tuple[str, bool]] = []

    def resultado(status: StatusIA, motivo: str, **extra) -> ResultadoIA:
        return ResultadoIA(status, motivo, bruta=bruta, verificacoes=verificacoes, **extra)

    try:
        dados = json.loads(bruta.texto)
    except (json.JSONDecodeError, TypeError):
        verificacoes.append(("JSON válido", False))
        return resultado(StatusIA.REJEITADA, "Resposta da IA não é JSON válido.")
    verificacoes.append(("JSON válido", True))

    erros = sorted(validador_resposta().iter_errors(dados), key=lambda e: list(e.path))
    if erros:
        verificacoes.append(("dentro do schema", False))
        return resultado(StatusIA.REJEITADA, f"Resposta fora do schema: {erros[0].message}", dados=dados)
    verificacoes.append(("dentro do schema", True))

    escolha = dados["combinacao_id"]
    if escolha == ABSTENCAO:
        verificacoes.append(("IA escolheu uma combinação", False))
        return resultado(
            StatusIA.ABSTENCAO,
            f"A IA não escolheu combinação: {dados['observacao_conferente']}",
            dados=dados,
        )

    permitidas = {c.id: c for c in opcoes}
    if escolha not in permitidas:
        verificacoes.append(("combinação entre as opções desta O.S.", False))
        return resultado(
            StatusIA.REJEITADA,
            f"A IA respondeu {escolha}, fora das opções permitidas ({', '.join(permitidas)}).",
            dados=dados,
        )
    verificacoes.append(("combinação entre as opções desta O.S.", True))

    if not trecho_esta_na_nota(dados["trecho_citado"], nota_mascarada):
        verificacoes.append(("trecho citado está na nota", False))
        return resultado(
            StatusIA.REJEITADA,
            "O trecho citado pela IA não está na nota do técnico.",
            dados=dados,
        )
    verificacoes.append(("trecho citado está na nota", True))

    if dados["confianca"] not in CONFIANCAS_ACEITAS:
        verificacoes.append(("confiança acima do limiar", False))
        return resultado(
            StatusIA.REJEITADA,
            f"Confiança '{dados['confianca']}' abaixo do limiar.",
            dados=dados,
        )
    verificacoes.append(("confiança acima do limiar", True))

    return resultado(StatusIA.ACEITA, "Classificação aceita.", dados=dados, combinacao=permitidas[escolha])
