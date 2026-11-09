"""Provedor real, testado sem rede.

1. Com um cliente falso: o que vai na chamada (modelo, schema, esforço) e
   como recusa e corte viram erro.
2. Com o SDK de verdade contra um servidor HTTP local: o pedido sai no formato
   da API e a resposta volta pelo mesmo caminho da produção. Nenhum byte sai
   da máquina.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from validador.catalogo import carregar_catalogo
from validador.decisao import decidir
from validador.ia.base import ErroDoProvedor, obter_provedor
from validador.ia.claude import MODELO_PADRAO, ProvedorClaude, custo_estimado_usd
from validador.modelos import Caminho

from .conftest import carregar

CAT = carregar_catalogo()
RESPOSTA_OK = json.dumps({
    "combinacao_id": "C13", "confianca": "alta",
    "trecho_citado": "Reconfigurei a rede da câmera e a imagem voltou",
    "observacao_conferente": "Falha de rede após troca de senha do Wi-Fi.",
}, ensure_ascii=False)


class ClienteFalso:
    def __init__(self, texto=RESPOSTA_OK, stop_reason="end_turn"):
        self.pedidos = []
        self.texto, self.stop_reason = texto, stop_reason
        self.messages = self

    def create(self, **kwargs):
        self.pedidos.append(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self.texto)],
            usage=SimpleNamespace(input_tokens=300, output_tokens=60),
        )


def test_modelo_padrao_e_o_mais_barato():
    assert MODELO_PADRAO == "claude-haiku-5-5"


def test_sem_chave_o_provedor_real_nao_sobe(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ErroDoProvedor, match="ANTHROPIC_API_KEY"):
        obter_provedor("anthropic")


def test_pedido_leva_schema_com_enum_e_esforco_baixo():
    cliente = ClienteFalso()
    provedor = ProvedorClaude(cliente=cliente)
    d = decidir(carregar("os-0007.json"), provedor)
    assert d.caminho is Caminho.PRONTA and d.combinacao.id == "C13"

    (pedido,) = cliente.pedidos
    assert pedido["model"] == "claude-haiku-5-5"
    formato = pedido["output_config"]["format"]
    assert formato["type"] == "json_schema"
    assert formato["schema"]["properties"]["combinacao_id"]["enum"] == ["C12", "C13", "C14", "NENHUMA"]
    assert pedido["output_config"]["effort"] == "low"
    mensagem = pedido["messages"][0]["content"]
    assert "Gabriela" not in mensagem and "98888" not in mensagem and "[TELEFONE]" in mensagem


def test_modelo_e_configuravel():
    cliente = ClienteFalso()
    ProvedorClaude(modelo="claude-sonnet-5-5", cliente=cliente).classificar(
        {"tipo_servico": "MANUTENCAO", "equipamentos": [], "nota_tecnico": "x"}, [CAT.combinacoes["C13"]]
    )
    assert cliente.pedidos[0]["model"] == "claude-sonnet-5-5"


@pytest.mark.parametrize("motivo", ["refusal", "max_tokens"])
def test_recusa_e_corte_viram_revisao_humana(motivo):
    provedor = ProvedorClaude(cliente=ClienteFalso(stop_reason=motivo))
    d = decidir(carregar("os-0007.json"), provedor)
    assert d.caminho is Caminho.REVISAO


def test_tokens_e_custo_sao_contabilizados():
    provedor = ProvedorClaude(cliente=ClienteFalso())
    bruta = provedor.classificar({"tipo_servico": "MANUTENCAO", "equipamentos": [], "nota_tecnico": "x"},
                                 [CAT.combinacoes["C13"]])
    assert (bruta.tokens_entrada, bruta.tokens_saida) == (300, 60)
    assert custo_estimado_usd("claude-haiku-5-5", 1_000_000, 0) == pytest.approx(0.10)
    assert custo_estimado_usd("modelo-sem-preco", 10, 10) is None


# --- SDK de verdade, servidor local -------------------------------------------

class _Stub(BaseHTTPRequestHandler):
    recebido: list[dict] = []

    def do_POST(self):  # noqa: N802 - nome exigido pelo http.server
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Stub.recebido.append({"caminho": self.path, "corpo": corpo})
        resposta = json.dumps({
            "id": "msg_local", "type": "message", "role": "assistant", "model": corpo["model"],
            "content": [{"type": "text", "text": RESPOSTA_OK}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 412, "output_tokens": 57},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resposta)))
        self.end_headers()
        self.wfile.write(resposta)

    def log_message(self, *args):
        pass


def test_sdk_real_contra_servidor_local():
    anthropic = pytest.importorskip("anthropic")
    servidor = HTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    try:
        cliente = anthropic.Anthropic(
            api_key="chave-de-teste", base_url=f"http://127.0.0.1:{servidor.server_port}", max_retries=0
        )
        d = decidir(carregar("os-0007.json"), ProvedorClaude(cliente=cliente))
    finally:
        servidor.shutdown()

    assert d.caminho is Caminho.PRONTA and d.ia.bruta.tokens_entrada == 412
    (pedido,) = _Stub.recebido
    assert pedido["caminho"] == "/v1/messages"
    corpo = pedido["corpo"]
    assert corpo["model"] == "claude-haiku-5-5"
    assert corpo["output_config"]["format"]["type"] == "json_schema"
    assert corpo["output_config"]["effort"] == "low"
    assert "Gabriela" not in json.dumps(corpo, ensure_ascii=False)
