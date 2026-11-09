"""Formatação legível no terminal. Sem dependências: ANSI puro, desligável."""

from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from typing import Any

from . import APROVACAO_FINAL
from .catalogo import carregar_catalogo
from .modelos import Caminho, Decisao, Severidade
from .regras import REGRAS

LARGURA = 92
CORES = {
    "negrito": "1", "fraco": "2", "vermelho": "31", "verde": "32",
    "amarelo": "33", "azul": "34", "magenta": "35", "ciano": "36",
}
COR_DO_CAMINHO = {Caminho.PRONTA: "verde", Caminho.CORRECAO: "vermelho", Caminho.REVISAO: "amarelo"}
CURTO = {Caminho.PRONTA.value: "PRONTA", Caminho.CORRECAO.value: "CORRECAO", Caminho.REVISAO.value: "REVISAO"}


def usar_cor(forcar: bool | None = None) -> bool:
    if forcar is not None:
        return forcar
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


class Estilo:
    def __init__(self, cor: bool):
        self.cor = cor

    def __call__(self, texto: str, *estilos: str) -> str:
        if not self.cor or not estilos:
            return texto
        codigos = ";".join(CORES[e] for e in estilos)
        return f"\033[{codigos}m{texto}\033[0m"


def _quebrar(texto: str, recuo: int, primeira: str = "") -> list[str]:
    espaco = " " * recuo
    linhas = textwrap.wrap(texto, width=LARGURA, initial_indent=espaco + primeira,
                           subsequent_indent=espaco + " " * len(primeira)) or [espaco + primeira]
    return linhas


MARCADOR = re.compile(r"\[(?:NOME|TELEFONE|EMAIL|CPF|CEP|ENDERECO)\]")


def _campos(pares: list[tuple[str, str]], recuo: int, s: Estilo) -> list[str]:
    """Chave e valor alinhados, valor quebrado em linhas e marcadores de máscara em destaque."""
    largura_chave = max(len(k) for k, _ in pares) + 2
    out = []
    for chave, valor in pares:
        linhas = textwrap.wrap(valor, width=LARGURA - recuo - largura_chave) or [""]
        for i, linha in enumerate(linhas):
            rotulo = f"{chave:<{largura_chave}}" if i == 0 else " " * largura_chave
            linha = MARCADOR.sub(lambda m: s(m.group(0), "magenta"), linha)
            out.append(" " * recuo + s(rotulo, "azul") + linha)
    return out


def _em_linhas(itens: list[tuple[str, str]], recuo: int) -> list[str]:
    """Empacota itens (texto visível, texto com ANSI) em linhas que cabem na largura."""
    out, atual, tamanho = [], [], 0
    for visivel, formatado in itens:
        if atual and tamanho + 3 + len(visivel) > LARGURA - recuo:
            out.append(" " * recuo + "   ".join(atual))
            atual, tamanho = [], 0
        atual.append(formatado)
        tamanho += len(visivel) + (3 if tamanho else 0)
    if atual:
        out.append(" " * recuo + "   ".join(atual))
    return out


def formatar_analise(ordem: dict[str, Any], d: Decisao, provedor: str, cor: bool = False) -> str:
    s = Estilo(cor)
    out: list[str] = []
    rotulo_provedor = provedor + (f" · {d.ia.bruta.modelo}" if d.ia and d.ia.bruta and d.ia.bruta.modelo else "")
    out.append(s(f"{d.os_id} · {ordem.get('tipo_servico', '?')}", "negrito") + s(f"   provedor: {rotulo_provedor}", "fraco"))
    out.append(s("─" * LARGURA, "fraco"))

    out.append(s("1  Pacote sanitizado", "negrito", "ciano") + s("  o que sai da máquina para a IA", "fraco"))
    if d.pacote:
        equipamentos = ", ".join(f"{e['categoria']} ({e['acao']})" for e in d.pacote.dados["equipamentos"])
        out += _campos([
            ("tipo_servico", d.pacote.dados["tipo_servico"]),
            ("equipamentos", equipamentos or "nenhum"),
            ("nota_tecnico", d.pacote.dados["nota_tecnico"]),
        ], 3, s)
        removidos = ", ".join(d.pacote.removidos)
        out += [s(linha, "fraco") for linha in _quebrar(removidos, 3, f"fora do pacote ({len(d.pacote.removidos)}): ")]
        if d.pacote.mascaras:
            mascaras = ", ".join(f"{n}× [{m}]" for m, n in sorted(d.pacote.mascaras.items()))
            out.append("   " + s("mascarado na nota: ", "fraco") + s(mascaras, "magenta"))
    else:
        out.append(s("   não montado: a O.S. parou antes da IA", "fraco"))
    out.append("")

    out.append(s("2  Regras determinísticas", "negrito", "ciano") + s(f"  {len(REGRAS)} regras, sem interpretação", "fraco"))
    if not d.achados:
        out.append("   " + s("✓", "verde") + " nenhuma pendência")
    for a in d.achados:
        marca, cor_sev = ("✗", "vermelho") if a.severidade is Severidade.BLOQUEIO else ("!", "amarelo")
        cabeca = f"{a.severidade.value:<8} {a.codigo}"
        out.append("   " + s(marca, cor_sev) + " " + s(cabeca, cor_sev))
        out += _quebrar(a.mensagem, 5)
        out.append("     " + s("evidência: " + json.dumps(a.evidencia, ensure_ascii=False), "fraco"))
    out.append("")

    if d.ia is None:
        out.append(s("3  IA em catálogo fechado", "negrito", "ciano") + s("  não chamada", "fraco"))
        motivo = "havia pendência verificável nas regras" if d.caminho is Caminho.CORRECAO else d.motivo
        out += [s(linha, "fraco") for linha in _quebrar(motivo, 3)]
    else:
        n = len(d.opcoes)
        out.append(s("3  IA em catálogo fechado", "negrito", "ciano")
                   + s(f"  {n} {'opção' if n == 1 else 'opções'} para esta O.S., de "
                       f"{len(carregar_catalogo().combinacoes)} no catálogo", "fraco"))
        for c in d.opcoes:
            out.append(s(f"   {c.id}", "azul") + f" {c.rotulo}")
        if d.ia.dados is not None:
            out.append(s("   resposta:", "fraco"))
            out += _campos([(k, str(v)) for k, v in d.ia.dados.items()], 5, s)
        elif d.ia.bruta is not None:
            out.append(s("   resposta crua: ", "fraco") + d.ia.bruta.texto[:200])
        if d.ia.verificacoes:
            itens = [(f"✓ {nome}", s("✓", "verde") + f" {nome}") if ok else
                     (f"✗ {nome}", s("✗", "vermelho") + f" {nome}") for nome, ok in d.ia.verificacoes]
            out += _em_linhas(itens, 3)
        if d.ia.status.value != "ACEITA":
            out += [s(linha, "amarelo") for linha in _quebrar(d.ia.motivo, 3)]
    out.append("")

    out.append(s("4  Decisão", "negrito", "ciano"))
    caminho = s(d.caminho.value, "negrito", COR_DO_CAMINHO[d.caminho])
    combinacao = f"  {d.combinacao.id} · {d.combinacao.rotulo}" if d.combinacao else ""
    out.append(f"   {caminho}{combinacao}")
    out += [s(linha, "fraco") for linha in _quebrar(d.motivo, 3)]
    if d.nota_ao_tecnico:
        out.append(s("   nota ao técnico:", "negrito"))
        out += ["   " + linha for linha in d.nota_ao_tecnico.splitlines()]
    if d.avisos_ao_conferente:
        out.append(s("   avisos ao conferente:", "negrito"))
        for aviso in d.avisos_ao_conferente:
            out += _quebrar(aviso, 3, "- ")
    out.append("")
    out.append(s("   " + APROVACAO_FINAL, "fraco"))
    return "\n".join(out)


def _num(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def formatar_avaliacao(r: dict[str, Any], cor: bool = False) -> str:
    s = Estilo(cor)
    m = r["metricas"]
    provedor = r["provedor"] + (f" · {r['modelo']}" if r.get("modelo") else "")
    out = [
        s(f"Avaliação · {r['total_os']} O.S. fictícias · provedor {provedor}", "negrito"),
        s("─" * LARGURA, "fraco"),
    ]

    def linha(nome: str, chave: str, nota: str, destaque: bool) -> str:
        v = m[chave]
        valor = f"{v['acertos']:>2}/{v['total']:<2}  {_num(v['pct']):>5}%"
        return f"   {nome:<15}" + (s(valor, "negrito") if destaque else valor) + s(f"   {nota}", "fraco")

    out.append(linha("Decisão", "decisao", "caminho escolhido, contra o gabarito", True))
    out.append(linha("Classificação", "classificacao", "combinação certa, nas O.S. que têm uma no gabarito", True))
    out.append(linha("Regras", "regras", "mesmo autor das regras e do gabarito: serve como regressão", False))
    out.append("")

    out.append(s("   Matriz de confusão", "negrito") + s("  linhas: gabarito · colunas: sistema", "fraco"))
    cab = "".join(f"{CURTO[c]:>10}" for c in r["matriz_confusao"])
    out.append(" " * 14 + s(cab, "fraco"))
    for esperado, linha_m in r["matriz_confusao"].items():
        celulas = ""
        for obtido, n in linha_m.items():
            texto = f"{n:>10}"
            celulas += s(texto, "verde" if obtido == esperado and n else ("vermelho" if n else "fraco"))
        out.append(f"   {CURTO[esperado]:<11}" + celulas)
    out.append("")

    erros = [c for c in r["casos"] if c["id"] in r["erros"]]
    out.append(s(f"   Erros ({len(erros)})", "negrito"))
    if not erros:
        out.append("   nenhum")
    for c in erros:
        esp = CURTO[c["decisao_esperada"]] + (f" {c['combinacao_esperada']}" if c["combinacao_esperada"] else "")
        obt = CURTO[c["decisao_obtida"]] + (f" {c['combinacao_obtida']}" if c["combinacao_obtida"] else "")
        out.append(f"   {s(c['id'], 'negrito')}  esperado {esp:<14} obtido {s(obt, 'vermelho')}")
        out += [s(linha, "fraco") for linha in _quebrar(c["motivo"], 12)]
    out.append("")

    u = r["uso"]
    custo = u["custo_estimado_usd"]
    custo_txt = "US$ 0 (offline)" if r["provedor"] == "falso" else (
        f"~US$ {custo:.4f}".replace(".", ",") if custo is not None else "preço do modelo não tabelado"
    )
    out.append(s(
        f"   {u['chamadas_ia']} chamadas à IA · {u['tokens_entrada']} tokens de entrada · "
        f"{u['tokens_saida']} de saída · {custo_txt}", "fraco"))
    return "\n".join(out)
