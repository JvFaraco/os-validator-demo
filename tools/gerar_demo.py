#!/usr/bin/env python3
"""Gera os dados da demo interativa (docs/dados.json).

Cada O.S. passa pelo `decidir` de verdade. A IA não é chamada: um provedor
"gravado" devolve a resposta que cada modelo deu na rodada versionada em
resultados/. Assim a página mostra o caminho real, com as respostas reais,
sem chave e sem rede. Se o caminho reproduzido não bater com o da rodada
salva, o script para com erro.

    python tools/gerar_demo.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from validador import APROVACAO_FINAL, DADOS, RESULTADOS  # noqa: E402
from validador.avaliacao import carregar_gabarito  # noqa: E402
from validador.catalogo import carregar_catalogo  # noqa: E402
from validador.decisao import carregar_ordem, decidir  # noqa: E402
from validador.guarda import trecho_com_instrucao  # noqa: E402
from validador.modelos import Caminho, Combinacao, Decisao, RespostaBruta  # noqa: E402
from validador.regras import CODIGOS  # noqa: E402

DESTINO = RAIZ / "docs" / "dados.json"

RODADAS = (
    ("haiku", "Claude Haiku 5.5", "avaliacao-anthropic-claude-haiku-5-5.json"),
    ("sonnet", "Claude Sonnet 5.5", "avaliacao-anthropic-claude-sonnet-5-5.json"),
    ("falso", "Falso (palavras-chave)", "avaliacao-falso.json"),
)

# O que cada regra confere, como na tabela do README.
REGRAS = {
    "NOTA_VAZIA": ("BLOQUEIO", "nota ausente ou com menos de 20 caracteres"),
    "RETIRADA_SEM_MOVIMENTACAO": ("BLOQUEIO", "equipamento retirado sem devolução ao estoque"),
    "COBRANCA_SEM_ACEITE": ("BLOQUEIO", "serviço cobrado sem comprovante de aceite"),
    "EQUIPAMENTO_NOVO_SEM_TESTE": ("BLOQUEIO", "equipamento instalado ou substituído sem teste registrado"),
    "TIPO_INCOMPATIVEL": ("BLOQUEIO", "desinstalação que instala, ou manutenção sem ação em equipamento"),
    "SERIE_REPETIDA": ("BLOQUEIO", "série do equipamento novo igual à do retirado"),
    "POUCAS_FOTOS": ("AVISO", "menos de 2 fotos"),
    "DURACAO_ATIPICA": ("AVISO", "atendimento com menos de 10 min ou mais de 8 h"),
}

LINHA_GABARITO = re.compile(r"^(OS-\d{4}):.*?#\s*(.+?)\s*$")


class ProvedorGravado:
    """Devolve a resposta salva para uma O.S., sem rede."""

    def __init__(self, nome: str, modelo: str | None, resposta: dict[str, Any] | None):
        self.nome = nome
        self.modelo = modelo
        self.resposta = resposta

    def classificar(self, pacote: dict[str, Any], opcoes: list[Combinacao]) -> RespostaBruta:
        if self.resposta is None:
            raise RuntimeError("a rodada salva não tem resposta da IA para esta O.S.")
        return RespostaBruta(json.dumps(self.resposta, ensure_ascii=False), self.nome, self.modelo)


def comentarios_do_gabarito() -> dict[str, str]:
    """Os comentários do gabarito dizem por que cada caso existe."""
    texto = (DADOS / "gabarito.yaml").read_text(encoding="utf-8")
    return {m.group(1): m.group(2) for m in map(LINHA_GABARITO.match, texto.splitlines()) if m}


def combinacao(c: Combinacao | None) -> dict[str, str] | None:
    return {"id": c.id, "equipamento": c.equipamento, "rotulo": c.rotulo} if c else None


def parada(d: Decisao, ordem: dict[str, Any]) -> str:
    """Etapa em que a O.S. saiu do fluxo, na ordem do `decidir`."""
    if d.caminho is Caminho.PRONTA:
        return "decisao"
    if d.caminho is Caminho.CORRECAO:
        return "regras"
    if d.ia is not None:
        return "validacao"
    if d.motivo.startswith("O.S. fora do contrato"):
        return "contrato"
    if not d.opcoes:
        return "catalogo"
    if trecho_com_instrucao(ordem.get("nota_tecnico") or ""):
        return "guarda"
    return "sanitizacao"


def trilha_comum(d: Decisao, ordem: dict[str, Any]) -> dict[str, Any]:
    """Tudo o que vem antes da IA: igual para qualquer provedor."""
    return {
        "achados": [
            {"codigo": a.codigo, "severidade": a.severidade.value, "mensagem": a.mensagem, "evidencia": a.evidencia}
            for a in d.achados
        ],
        "opcoes": [combinacao(c) for c in d.opcoes],
        "guarda": trecho_com_instrucao(ordem.get("nota_tecnico") or "") if d.opcoes else None,
        "pacote": {
            "dados": d.pacote.dados,
            "removidos": d.pacote.removidos,
            "mascaras": d.pacote.mascaras,
        } if d.pacote else None,
    }


def trilha_do_provedor(d: Decisao, ordem: dict[str, Any]) -> dict[str, Any]:
    ia = None
    if d.ia is not None:
        ia = {
            "status": d.ia.status.value,
            "motivo": d.ia.motivo,
            "resposta": d.ia.dados,
            "verificacoes": [[nome, ok] for nome, ok in d.ia.verificacoes],
        }
    return {
        "parada": parada(d, ordem),
        "ia": ia,
        "caminho": d.caminho.value,
        "motivo": d.motivo,
        "combinacao": combinacao(d.combinacao),
        "nota_ao_tecnico": d.nota_ao_tecnico,
        "avisos": d.avisos_ao_conferente,
    }


def montar() -> dict[str, Any]:
    catalogo = carregar_catalogo()
    gabarito = carregar_gabarito()
    comentarios = comentarios_do_gabarito()
    rodadas = {
        chave: (rotulo, json.loads((RESULTADOS / arquivo).read_text(encoding="utf-8")))
        for chave, rotulo, arquivo in RODADAS
    }

    ordens = []
    for arquivo in sorted((DADOS / "ordens").glob("os-*.json")):
        ordem = carregar_ordem(arquivo)
        os_id = ordem["id"]
        comum: dict[str, Any] | None = None
        por_provedor = {}
        for chave, (_, relatorio) in rodadas.items():
            caso = next(c for c in relatorio["casos"] if c["id"] == os_id)
            provedor = ProvedorGravado(relatorio["provedor"], relatorio.get("modelo"), caso["ia_resposta"])
            d = decidir(ordem, provedor, catalogo)
            obtido = (d.caminho.value, d.combinacao.id if d.combinacao else None,
                      d.ia.status.value if d.ia else "NAO_CHAMADA")
            salvo = (caso["decisao_obtida"], caso["combinacao_obtida"], caso["ia"])
            if obtido != salvo:
                raise SystemExit(f"{os_id} ({chave}): reproduzido {obtido}, rodada salva {salvo}")
            comum = comum or trilha_comum(d, ordem)
            por_provedor[chave] = trilha_do_provedor(d, ordem)

        g = gabarito[os_id]
        ordens.append({
            "id": os_id,
            "ordem": ordem,
            "gabarito": {
                "decisao": g["decisao"],
                "combinacao": g.get("combinacao"),
                "regras": sorted(g.get("regras", [])),
                "comentario": comentarios.get(os_id),
            },
            **comum,
            "por_provedor": por_provedor,
        })

    return {
        "gerado_por": "python tools/gerar_demo.py",
        "aprovacao_final": APROVACAO_FINAL,
        "catalogo": {
            "total": len(catalogo.combinacoes),
            "equipamentos": catalogo.equipamentos,
        },
        "regras": [
            {"codigo": codigo, "severidade": REGRAS[codigo][0], "descricao": REGRAS[codigo][1]}
            for codigo in CODIGOS
        ],
        "provedores": [
            {
                "id": chave,
                "rotulo": rotulo,
                "modelo": relatorio.get("modelo"),
                "rodada": relatorio["gerado_em"],
                "metricas": relatorio["metricas"],
                "uso": relatorio["uso"],
                "erros": relatorio["erros"],
            }
            for chave, (rotulo, relatorio) in rodadas.items()
        ],
        "ordens": ordens,
    }


def serializar(dados: dict[str, Any]) -> str:
    return json.dumps(dados, ensure_ascii=False, indent=1) + "\n"


def main() -> int:
    if set(REGRAS) != set(CODIGOS):
        raise SystemExit("REGRAS deste script está fora de sincronia com validador.regras.CODIGOS")
    texto = serializar(montar())
    DESTINO.write_text(texto, encoding="utf-8", newline="\n")
    print(f"{DESTINO.relative_to(RAIZ)}: {len(texto.encode('utf-8')) // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
