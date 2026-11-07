import json

import pytest

from aberto import CLIENTE, PROFESSOR, ClienteAberto, ProfessorAberto, WorkersAI
from cenarios import gerar
from conversa import Recusa
from custo import Uso
from prompts import FRASE_HUMANO
from sistema import NOMES, ferramentas_anthropic, ferramentas_openai


class APIFalsa:
    def __init__(self, respostas):
        self.respostas = iter(respostas)
        self.chamadas = []

    def completar(self, **corpo):
        self.chamadas.append(json.loads(json.dumps(corpo)))  # cópia, porque a lista de mensagens segue crescendo
        return next(self.respostas)


def resposta(texto="", chamadas=(), fim="stop", entrada=100, saida=20):
    msg = {"role": "assistant", "content": texto}
    if chamadas:
        msg["tool_calls"] = [{"id": i, "type": "function", "function": {"name": n, "arguments": a}}
                             for i, n, a in chamadas]
    return {"choices": [{"message": msg, "finish_reason": fim}],
            "usage": {"prompt_tokens": entrada, "completion_tokens": saida}}


def test_custo_workers_ai():
    assert Uso(PROFESSOR, entrada=1_000_000, saida=1_000_000).custo() == pytest.approx(1.50)
    assert Uso(PROFESSOR, cache_leitura=1_000_000).custo() == pytest.approx(0.006)
    assert CLIENTE == PROFESSOR


def test_uso_soma_formato_openai():
    u = Uso(PROFESSOR)
    u.somar({"prompt_tokens": 100, "completion_tokens": 20})
    assert (u.entrada, u.saida) == (100, 20)
    u.somar({"prompt_tokens": 100, "completion_tokens": 5, "prompt_tokens_details": {"cached_tokens": 80}})
    assert (u.entrada, u.saida, u.cache_leitura) == (120, 25, 80)


def test_ferramentas_openai_tem_as_descricoes_longas():
    fs = ferramentas_openai()
    assert tuple(f["function"]["name"] for f in fs) == NOMES
    assert [f["function"]["description"] for f in fs] == [t["description"] for t in ferramentas_anthropic()]


def test_professor_monta_a_conversa_no_formato_openai():
    api = APIFalsa([resposta(chamadas=[("c1", "rastrear_entrega", '{"pedido_id": "P1"}')], fim="tool_calls"),
                    resposta("Está a caminho.")])
    p = ProfessorAberto(api)
    turno = p.passo([{"papel": "contexto", "texto": "ctx"}, {"papel": "cliente", "texto": "cadê?"}])
    assert turno == {"texto": "", "chamadas": [{"id": "c1", "nome": "rastrear_entrega", "args": {"pedido_id": "P1"}}]}
    turno = p.passo([{"papel": "ferramenta", "id": "c1", "nome": "rastrear_entrega", "resultado": {"r": "Pão"}}])
    assert turno == {"texto": "Está a caminho.", "chamadas": []}

    msgs = api.chamadas[1]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool"]
    assert "Garfo Ligeiro" in msgs[0]["content"]
    assert msgs[1]["content"] == "ctx\n\ncadê?"
    assert msgs[2]["tool_calls"][0]["function"]["name"] == "rastrear_entrega"
    assert msgs[3] == {"role": "tool", "tool_call_id": "c1", "content": '{"r": "Pão"}'}
    assert p.uso.entrada == 200 and p.uso.saida == 40


def test_professor_pede_ferramentas_e_raciocinio_baixo():
    api = APIFalsa([resposta("oi")])
    ProfessorAberto(api).passo([{"papel": "cliente", "texto": "oi"}])
    corpo = api.chamadas[0]
    assert corpo["model"] == PROFESSOR == "@cf/deepseek-ai/deepseek-v4.1-flash-1017"
    assert corpo["tools"] == ferramentas_openai() and corpo["tool_choice"] == "auto"
    assert corpo["reasoning_effort"] == "low"


def test_resposta_cortada_vira_recusa():
    with pytest.raises(Recusa):
        ProfessorAberto(APIFalsa([resposta("", fim="length")])).passo([{"papel": "cliente", "texto": "oi"}])


def test_argumentos_que_nao_sao_json_viram_erro_no_sistema():
    api = APIFalsa([resposta(chamadas=[("c1", "reembolsar", "{nao é json")], fim="tool_calls")])
    turno = ProfessorAberto(api).passo([{"papel": "cliente", "texto": "oi"}])
    assert turno["chamadas"][0]["args"] == {"_argumentos_invalidos": "{nao é json"}


def test_cliente_aberto_encerra_com_fim_e_nao_pede_humano():
    api = APIFalsa([resposta("cadê meu pedido?"), resposta("valeu! [FIM]")])
    cli = ClienteAberto(api, gerar(1, "status"))
    assert cli.falar(None) == "cadê meu pedido?"
    assert cli.falar("Está a caminho.") is None
    assert api.chamadas[0]["model"] == CLIENTE
    assert api.chamadas[0]["reasoning_effort"] == "none"  # o cliente só fala; raciocínio é custo à toa
    assert FRASE_HUMANO in api.chamadas[0]["messages"][0]["content"]
    assert [m["role"] for m in api.chamadas[1]["messages"]] == ["system", "user", "assistant", "user"]
    assert FRASE_HUMANO not in ClienteAberto(APIFalsa([]), gerar(1, "humano")).sistema


class Resp:
    def __init__(self, status, corpo=None):
        self.status_code, self.corpo, self.text = status, corpo or {}, str(corpo)

    def json(self):
        return self.corpo


class SessaoFalsa:
    def __init__(self, respostas):
        self.respostas, self.headers, self.posts = iter(respostas), {}, []

    def post(self, url, json, timeout):
        self.posts.append(url)
        r = next(self.respostas)
        if isinstance(r, Exception):
            raise r
        return r


def test_workers_ai_tenta_de_novo_em_erro_passageiro():
    import requests
    ok = resposta("oi")
    s = SessaoFalsa([Resp(429), requests.ConnectionError("caiu"), Resp(200, ok)])
    api = WorkersAI("conta1", "tok", sessao=s, espera=0)
    assert api.completar(model="m", messages=[]) == ok
    assert s.posts[0] == "https://api.cloudflare.com/client/v4/accounts/conta1/ai/v1/chat/completions"
    assert s.headers["Authorization"] == "Bearer tok"


def test_workers_ai_desiste_e_nao_mostra_o_token():
    s = SessaoFalsa([Resp(500)] * 4)
    with pytest.raises(RuntimeError) as e:
        WorkersAI("conta1", "segredo123", sessao=s, espera=0, tentativas=4).completar(model="m", messages=[])
    assert "segredo123" not in str(e.value)
    with pytest.raises(RuntimeError):
        WorkersAI("c", "t", sessao=SessaoFalsa([Resp(400, {"errors": ["x"]})]), espera=0).completar(model="m")
