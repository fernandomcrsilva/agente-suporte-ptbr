import json

from juiz import RUBRICA, julgar, transcricao_para_juiz
from test_claude import APIFalsa, resposta, texto

EVENTOS = [
    {"papel": "contexto", "texto": "Cliente logado: Ana (C1). Agora: 07/11 20:30."},
    {"papel": "cliente", "texto": "Meu pedido atrasou."},
    {"papel": "agente", "texto": "Vou verificar.", "chamadas": [{"id": "c1", "nome": "listar_pedidos", "args": {}}]},
    {"papel": "ferramenta", "id": "c1", "nome": "listar_pedidos", "resultado": {"pedidos": ["x" * 400]}},
    {"papel": "agente", "texto": "Seu pedido atrasou 50 minutos. Dei um cupom de R$ 20.", "chamadas": []},
]
NOTA = {"clareza": 5, "tom": 4, "explicou_decisao": True, "prometeu_sem_cumprir": False, "comentario": "Bom."}


def test_transcricao_e_cega():
    t = transcricao_para_juiz(EVENTOS)
    for proibido in ("Cliente logado", "aluno", "esperado", "Qwen", "deepseek", "claude"):
        assert proibido not in t
    assert t.splitlines()[0] == "Cliente: Meu pedido atrasou."
    assert t.splitlines()[-1] == "Atendente: Seu pedido atrasou 50 minutos. Dei um cupom de R$ 20."
    linha = t.splitlines()[1]
    assert linha.startswith("[ferramenta listar_pedidos: ") and len(linha) <= len("[ferramenta listar_pedidos: ]") + 300
    assert transcricao_para_juiz(EVENTOS) == t


def test_juiz_pede_json_com_a_rubrica():
    api = APIFalsa([resposta(texto(json.dumps(NOTA)))])
    julgar(api, EVENTOS)
    kw = api.chamadas[0]
    assert kw["model"] == "claude-sonnet-5-5" and kw["max_tokens"] == 2000
    assert kw["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": RUBRICA}}
    assert "delivery" in kw["system"]
    assert RUBRICA["additionalProperties"] is False and set(RUBRICA["required"]) == set(RUBRICA["properties"])


def test_juiz_le_o_json():
    nota, uso = julgar(APIFalsa([resposta(texto(json.dumps(NOTA)), entrada=1000, saida=100)]), EVENTOS)
    assert nota == NOTA
    assert uso.modelo == "claude-sonnet-5-5" and uso.entrada == 1000 and uso.saida == 100


def test_recusa_vira_none():
    nota, uso = julgar(APIFalsa([resposta(texto(""), stop="refusal")]), EVENTOS)
    assert nota is None and uso.saida == 20


def test_juiz_ve_so_o_que_o_cliente_leu():
    assert "Vou verificar" not in transcricao_para_juiz(EVENTOS)  # fala com chamada não chega ao cliente
    transferiu = EVENTOS[:2] + [
        {"papel": "agente", "texto": "", "chamadas": [{"id": "c9", "nome": "transferir_para_humano", "args": {}}]},
        {"papel": "ferramenta", "id": "c9", "nome": "transferir_para_humano", "resultado": {"ok": True}},
        {"papel": "agente", "texto": "Já te passei para um colega.", "chamadas": [{"id": "c10", "nome": "x", "args": {}}]}]
    assert transcricao_para_juiz(transferiu).endswith("Atendente: Já te passei para um colega.")  # a despedida conta
