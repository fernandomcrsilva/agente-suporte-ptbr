import pytest

from aluno import SISTEMA_ALUNO, AgenteQwen, sistema_completo
from conversa import rodar
from fabrica import antes, cenario, pedido
from test_conversa import ClienteRoteiro


@pytest.fixture(scope="module")
def tok():
    try:
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B", local_files_only=True)
    except Exception as e:
        pytest.skip(f"tokenizer indisponível: {e}")


class ModeloFalso:
    def __init__(self, tok, saidas):
        self.tok, self.saidas, self.prompts = tok, iter(saidas), []

    def gerar(self, ids):
        self.prompts.append(ids)
        return next(self.saidas)


SAIDAS = ['<tool_call>\n{"name": "listar_pedidos", "arguments": {}}\n</tool_call><|im_end|>', "Achei.<|im_end|>"]
C = cenario("status", [pedido(status="a_caminho", previsto=antes(m=10))])


def test_aluno_conversa_com_ferramenta(tok):
    conv = rodar(C, AgenteQwen(ModeloFalso(tok, SAIDAS), SISTEMA_ALUNO), ClienteRoteiro(["cadê?"]))
    assert conv.motivo_fim == "cliente_encerrou"
    assert [e["nome"] for e in conv.eventos if e["papel"] == "ferramenta"] == ["listar_pedidos"]
    assert conv.eventos[-1] == {"papel": "agente", "texto": "Achei.", "chamadas": []}


def test_segunda_geracao_ve_o_resultado(tok):
    m = ModeloFalso(tok, SAIDAS)
    rodar(C, AgenteQwen(m, SISTEMA_ALUNO), ClienteRoteiro(["cadê?"]))
    segundo = tok.decode(m.prompts[1])
    assert "<tool_response>" in segundo and '"name": "listar_pedidos"' in segundo


def test_sistema_escolhido_vai_no_prompt(tok):
    m = ModeloFalso(tok, SAIDAS)
    rodar(C, AgenteQwen(m, sistema_completo()), ClienteRoteiro(["cadê?"]))
    assert "R$ 80" in tok.decode(m.prompts[0])
    m = ModeloFalso(tok, SAIDAS)
    rodar(C, AgenteQwen(m, SISTEMA_ALUNO), ClienteRoteiro(["cadê?"]))
    assert "R$ 80" not in tok.decode(m.prompts[0])
