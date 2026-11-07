import json
from types import SimpleNamespace

import pytest

from cenarios import gerar
from claude import FRASE_HUMANO, PROMPTS, ClienteSimulado, Professor, Uso, mensagem_usuario
from conversa import Recusa


class APIFalsa:
    def __init__(self, respostas):
        self.respostas = iter(respostas)
        self.chamadas = []
        self.messages = self

    def create(self, **kw):
        self.chamadas.append(kw)
        return next(self.respostas)


def resposta(*blocos, stop="end_turn", entrada=100, saida=20):
    uso = SimpleNamespace(input_tokens=entrada, output_tokens=saida, cache_read_input_tokens=50,
                          cache_creation_input_tokens=None)
    return SimpleNamespace(content=list(blocos), stop_reason=stop, usage=uso)


def texto(t):
    return SimpleNamespace(type="text", text=t)


def ferramenta(id, nome, args):
    return SimpleNamespace(type="tool_use", id=id, name=nome, input=args)


def test_custo():
    assert Uso("claude-opus-5-5", entrada=1_000_000, saida=1_000_000).custo() == pytest.approx(24.0)
    assert Uso("claude-opus-5-5", cache_leitura=1_000_000).custo() == pytest.approx(0.20)


def test_mensagem_usuario_ferramenta():
    m = mensagem_usuario([{"papel": "ferramenta", "id": "t1", "nome": "x", "resultado": {"restaurante": "Pão"}}])
    assert m["role"] == "user"
    bloco = m["content"][0]
    assert bloco["type"] == "tool_result" and bloco["tool_use_id"] == "t1"
    assert '"Pão"' in bloco["content"] and json.loads(bloco["content"]) == {"restaurante": "Pão"}

    erro = mensagem_usuario([{"papel": "ferramenta", "id": "t2", "nome": "x", "resultado": {"erro": "não"}}])
    assert erro["content"][0]["is_error"] is True


def test_mensagem_usuario_texto():
    m = mensagem_usuario([{"papel": "contexto", "texto": "ctx"}, {"papel": "cliente", "texto": "oi"}])
    assert m["content"] == [{"type": "text", "text": "ctx"}, {"type": "text", "text": "oi"}]


def test_professor_guarda_resposta_inteira():
    r = resposta(texto("Vou ver."), ferramenta("t1", "rastrear_entrega", {"pedido_id": "P1"}), stop="tool_use")
    p = Professor(APIFalsa([r]))
    turno = p.passo([{"papel": "cliente", "texto": "cadê?"}])
    assert turno == {"texto": "Vou ver.", "chamadas": [{"id": "t1", "nome": "rastrear_entrega",
                                                        "args": {"pedido_id": "P1"}}]}
    assert p.mensagens[-1]["content"] is r.content
    assert p.uso.entrada == 100 and p.uso.saida == 20 and p.uso.cache_leitura == 50


def test_professor_sem_fallback_e_tool_choice_auto():
    api = APIFalsa([resposta(texto("oi"))])
    p = Professor(api)
    p.passo([{"papel": "cliente", "texto": "oi"}])
    kw = api.chamadas[0]
    assert "fallbacks" not in kw and "betas" not in kw
    assert kw["tool_choice"] == {"type": "auto"}
    assert kw["model"] == "claude-opus-5-5" and kw["output_config"] == {"effort": "low"}
    assert all(t["strict"] for t in kw["tools"])
    assert "Garfo Ligeiro" in kw["system"] and "{EMPRESA}" not in kw["system"]


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_recusa(stop):
    with pytest.raises(Recusa):
        Professor(APIFalsa([resposta(texto(""), stop=stop)])).passo([{"papel": "cliente", "texto": "oi"}])


def test_cliente_encerra_com_fim():
    api = APIFalsa([resposta(texto("cadê meu pedido?")), resposta(texto("valeu! [FIM]"))])
    cli = ClienteSimulado(api, gerar(1, "status"))
    assert cli.falar(None) == "cadê meu pedido?"
    assert cli.falar("Está a caminho.") is None
    assert api.chamadas[0]["model"] == "claude-haiku-5-5"
    msgs = api.chamadas[1]["messages"]  # a mesma lista, que segue crescendo depois da chamada
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[2] == {"role": "user", "content": "Está a caminho."}


def test_cliente_nunca_pede_humano():
    assert FRASE_HUMANO == "Nunca peça para falar com um humano."
    assert FRASE_HUMANO in ClienteSimulado(APIFalsa([]), gerar(1, "atraso")).sistema
    assert FRASE_HUMANO not in ClienteSimulado(APIFalsa([]), gerar(1, "humano")).sistema


def test_cliente_recebe_fatos_e_objetivo():
    c = gerar(2, "item")
    s = ClienteSimulado(APIFalsa([]), c).sistema
    assert c.nome in s and c.alvo().restaurante in s and "{" not in s


def test_prompt_professor_tem_os_numeros():
    p = (PROMPTS / "professor.md").read_text()
    for trecho in ("R$ 10", "R$ 20", "R$ 80", "20 minutos", "45 minutos", "48 horas", "60 minutos", '"todos"'):
        assert trecho in p, trecho
