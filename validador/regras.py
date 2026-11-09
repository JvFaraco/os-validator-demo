"""Regras determinísticas: tudo o que dá para conferir sem interpretar texto.

Cada regra recebe a O.S. inteira (dados pessoais inclusive: elas rodam na
máquina e nada daqui sai para a IA) e devolve zero ou mais achados com a
evidência que os sustenta. `BLOQUEIO` devolve a O.S. ao técnico;
`AVISO` segue ao conferente, escrito na O.S.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from .catalogo import Catalogo, carregar_catalogo
from .modelos import Achado, Severidade

MIN_CARACTERES_NOTA = 20
MIN_FOTOS = 2
DURACAO_MIN_MINUTOS = 10
DURACAO_MAX_MINUTOS = 8 * 60

ACOES_QUE_RETIRAM = {"SUBSTITUIDO", "RETIRADO"}
ACOES_QUE_INSTALAM = {"SUBSTITUIDO", "INSTALADO"}

Regra = Callable[[dict[str, Any], Catalogo], list[Achado]]


def nota_vazia(ordem: dict[str, Any], catalogo: Catalogo) -> list[Achado]:
    nota = (ordem.get("nota_tecnico") or "").strip()
    if len(nota) >= MIN_CARACTERES_NOTA:
        return []
    return [Achado(
        "NOTA_VAZIA", Severidade.BLOQUEIO,
        f"Descreva na nota o que encontrou e o que fez (a nota tem {len(nota)} "
        f"caractere(s); o mínimo é {MIN_CARACTERES_NOTA}).",
        {"caracteres": len(nota)},
    )]


def retirada_sem_movimentacao(ordem: dict[str, Any], catalogo: Catalogo) -> list[Achado]:
    movimentadas = {m["serie"] for m in ordem.get("movimentacoes_estoque", [])}
    achados = []
    for equipamento in ordem.get("equipamentos", []):
        serie = equipamento.get("serie_retirada")
        if equipamento["acao"] in ACOES_QUE_RETIRAM and serie and serie not in movimentadas:
            nome = catalogo.nome_equipamento(equipamento["categoria"])
            achados.append(Achado(
                "RETIRADA_SEM_MOVIMENTACAO", Severidade.BLOQUEIO,
                f"Registre a devolução ao estoque do equipamento retirado: {nome}, série {serie}.",
                {"serie": serie, "categoria": equipamento["categoria"]},
            ))
    return achados


def cobranca_sem_aceite(ordem: dict[str, Any], catalogo: Catalogo) -> list[Achado]:
    cobranca = ordem.get("cobranca") or {}
    if not cobranca.get("cobrado") or ordem.get("comprovante_aceite"):
        return []
    valor = cobranca.get("valor", 0)
    reais = f"{valor:.2f}".replace(".", ",")
    return [Achado(
        "COBRANCA_SEM_ACEITE", Severidade.BLOQUEIO,
        f"Anexe o comprovante de aceite do cliente para a cobrança de R$ {reais}.",
        {"valor": valor, "comprovante_aceite": False},
    )]


def equipamento_novo_sem_teste(ordem: dict[str, Any], catalogo: Catalogo) -> list[Achado]:
    achados = []
    for equipamento in ordem.get("equipamentos", []):
        if equipamento["acao"] in ACOES_QUE_INSTALAM and not equipamento.get("teste_registrado"):
            nome = catalogo.nome_equipamento(equipamento["categoria"])
            serie = equipamento.get("serie_instalada", "sem série")
            achados.append(Achado(
                "EQUIPAMENTO_NOVO_SEM_TESTE", Severidade.BLOQUEIO,
                f"Registre o teste funcional do equipamento novo: {nome}, série {serie}.",
                {"serie": serie, "categoria": equipamento["categoria"]},
            ))
    return achados


def tipo_incompativel(ordem: dict[str, Any], catalogo: Catalogo) -> list[Achado]:
    tipo = ordem["tipo_servico"]
    equipamentos = ordem.get("equipamentos", [])
    if tipo == "DESINSTALACAO":
        instalados = [e for e in equipamentos if e["acao"] in ACOES_QUE_INSTALAM]
        if instalados:
            e = instalados[0]
            return [Achado(
                "TIPO_INCOMPATIVEL", Severidade.BLOQUEIO,
                f"Desinstalação não instala equipamento: confira o tipo da O.S. ou o "
                f"registro de {catalogo.nome_equipamento(e['categoria'])} ({e['acao']}).",
                {"tipo_servico": tipo, "categoria": e["categoria"], "acao": e["acao"]},
            )]
    if tipo == "MANUTENCAO" and not equipamentos:
        return [Achado(
            "TIPO_INCOMPATIVEL", Severidade.BLOQUEIO,
            "Manutenção sem ação em nenhum equipamento: registre o que foi feito "
            "ou corrija o tipo da O.S.",
            {"tipo_servico": tipo, "equipamentos": 0},
        )]
    return []


def serie_repetida(ordem: dict[str, Any], catalogo: Catalogo) -> list[Achado]:
    achados = []
    for equipamento in ordem.get("equipamentos", []):
        retirada, instalada = equipamento.get("serie_retirada"), equipamento.get("serie_instalada")
        if equipamento["acao"] == "SUBSTITUIDO" and retirada and retirada == instalada:
            nome = catalogo.nome_equipamento(equipamento["categoria"])
            achados.append(Achado(
                "SERIE_REPETIDA", Severidade.BLOQUEIO,
                f"A série do equipamento novo ({nome}) é igual à do retirado ({retirada}): "
                "confira a série instalada.",
                {"serie_retirada": retirada, "serie_instalada": instalada},
            ))
    return achados


def poucas_fotos(ordem: dict[str, Any], catalogo: Catalogo) -> list[Achado]:
    fotos = ordem.get("fotos", 0)
    if fotos >= MIN_FOTOS:
        return []
    quantas = "Nenhuma foto anexada" if fotos == 0 else ("Só 1 foto anexada" if fotos == 1 else f"Só {fotos} fotos anexadas")
    return [Achado(
        "POUCAS_FOTOS", Severidade.AVISO,
        f"{quantas}; o padrão é pelo menos {MIN_FOTOS}.",
        {"fotos": fotos},
    )]


def duracao_atipica(ordem: dict[str, Any], catalogo: Catalogo) -> list[Achado]:
    atendimento = ordem.get("atendimento") or {}
    try:
        inicio = datetime.fromisoformat(atendimento["inicio"])
        fim = datetime.fromisoformat(atendimento["fim"])
    except (KeyError, TypeError, ValueError):
        return []
    minutos = round((fim - inicio).total_seconds() / 60)
    if DURACAO_MIN_MINUTOS <= minutos <= DURACAO_MAX_MINUTOS:
        return []
    return [Achado(
        "DURACAO_ATIPICA", Severidade.AVISO,
        f"Atendimento de {minutos} min, fora da faixa usual "
        f"({DURACAO_MIN_MINUTOS} min a {DURACAO_MAX_MINUTOS // 60} h).",
        {"minutos": minutos},
    )]


REGRAS: tuple[Regra, ...] = (
    nota_vazia,
    retirada_sem_movimentacao,
    cobranca_sem_aceite,
    equipamento_novo_sem_teste,
    tipo_incompativel,
    serie_repetida,
    poucas_fotos,
    duracao_atipica,
)

CODIGOS = (
    "NOTA_VAZIA", "RETIRADA_SEM_MOVIMENTACAO", "COBRANCA_SEM_ACEITE",
    "EQUIPAMENTO_NOVO_SEM_TESTE", "TIPO_INCOMPATIVEL", "SERIE_REPETIDA",
    "POUCAS_FOTOS", "DURACAO_ATIPICA",
)


def avaliar_regras(ordem: dict[str, Any], catalogo: Catalogo | None = None) -> list[Achado]:
    catalogo = catalogo or carregar_catalogo()
    achados: list[Achado] = []
    for regra in REGRAS:
        achados.extend(regra(ordem, catalogo))
    return achados
