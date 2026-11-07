import pytest

from formato_qwen import INICIO_AGENTE, PROMPT_ALUNO, corpo, interpretar, prompt_geracao, prompt_sistema, renderizar
from sistema import NOMES


@pytest.fixture(scope="module")
def tok():
    try:
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained("Qwen/Qwen3-1.7B", local_files_only=True)
    except Exception as e:  # sem o tokenizer no cache local
        pytest.skip(f"tokenizer indisponível: {e}")


CHAMADA = {"id": "t1", "nome": "rastrear_entrega", "args": {"pedido_id": "P1"}}
EVENTOS = [
    {"papel": "contexto", "texto": "Cliente logado: Ana (C1). Agora: 07/11 20:00."},
    {"papel": "cliente", "texto": "cadê meu pedido?"},
    {"papel": "agente", "texto": "", "chamadas": [CHAMADA]},
    {"papel": "ferramenta", "id": "t1", "nome": "rastrear_entrega", "resultado": {"restaurante": "Pão & Cia"}},
    {"papel": "agente", "texto": "Está a caminho.", "chamadas": []},
    {"papel": "cliente", "texto": "valeu"},
    {"papel": "agente", "texto": "Vou conferir de novo.", "chamadas": [CHAMADA, dict(CHAMADA, id="t2")]},
]


def test_sistema_traz_ferramentas(tok):
    s = prompt_sistema(tok)
    assert s.startswith("<|im_start|>system\n" + PROMPT_ALUNO)
    assert "<tools>" in s and all(n in s for n in NOMES)


def test_rotulos_cobrem_so_o_agente(tok):
    ids, rotulos = renderizar(EVENTOS, tok)
    assert len(ids) == len(rotulos)
    alvo = "".join(corpo(e) + "<|im_end|>" for e in EVENTOS if e["papel"] == "agente")
    assert tok.decode([i for i, r in zip(ids, rotulos) if r != -100]) == alvo
    assert all(r in (-100, i) for i, r in zip(ids, rotulos))


def test_contexto_vai_junto_com_a_primeira_fala(tok):
    texto = tok.decode(renderizar(EVENTOS, tok)[0])
    assert "<|im_start|>user\nCliente logado: Ana (C1). Agora: 07/11 20:00.\n\ncadê meu pedido?<|im_end|>" in texto
    assert texto.count(INICIO_AGENTE) == 3


def test_chamada_no_formato_do_qwen(tok):
    nativo = tok.apply_chat_template(
        [{"role": "user", "content": "oi"},
         {"role": "assistant", "content": "Vou conferir de novo.", "tool_calls": [
             {"type": "function", "function": {"name": "rastrear_entrega", "arguments": {"pedido_id": "P1"}}}] * 2},
         {"role": "tool", "content": '{"a": 1}'}, {"role": "tool", "content": '{"b": 2}'}],
        tokenize=False)
    assert corpo(EVENTOS[-1]) in nativo
    meu = tok.decode(renderizar([EVENTOS[1], EVENTOS[2],
                                 {"papel": "ferramenta", "resultado": {"a": 1}},
                                 {"papel": "ferramenta", "resultado": {"b": 2}}], tok)[0])
    trecho = '<|im_start|>user\n<tool_response>\n{"a": 1}\n</tool_response>\n<tool_response>\n{"b": 2}\n</tool_response><|im_end|>'
    assert trecho in nativo and trecho in meu


def test_acentos_sem_escape(tok):
    texto = tok.decode(renderizar(EVENTOS, tok)[0])
    assert "Pão & Cia" in texto and "\\u00e3" not in texto


def test_prompt_geracao_termina_no_inicio_do_agente(tok):
    texto = tok.decode(prompt_geracao(EVENTOS[:2], tok))
    assert texto.endswith("cadê meu pedido?<|im_end|>\n" + INICIO_AGENTE)


def test_interpreta_texto_puro():
    assert interpretar("Oi!<|im_end|>lixo depois", "q") == {"texto": "Oi!", "chamadas": []}


def test_interpreta_duas_chamadas():
    saida = ('<tool_call>\n{"name": "listar_pedidos", "arguments": {}}\n</tool_call>\n'
             '<tool_call>\n{"name": "rastrear_entrega", "arguments": {"pedido_id": "P1"}}\n</tool_call><|im_end|>')
    assert interpretar(saida, "q") == {"texto": "", "chamadas": [
        {"id": "q0", "nome": "listar_pedidos", "args": {}},
        {"id": "q1", "nome": "rastrear_entrega", "args": {"pedido_id": "P1"}}]}


def test_chamada_sem_fechamento():
    r = interpretar('Vou ver.\n<tool_call>\n{"name": "listar_pedidos", "arguments": {}}', "x")
    assert r == {"texto": "Vou ver.", "chamadas": [{"id": "x0", "nome": "listar_pedidos", "args": {}}]}


def test_think_perdido_some():
    assert interpretar("<think>\nhmm\n</think>\n\nOlá!<|im_end|>", "q")["texto"] == "Olá!"


def test_json_invalido_vira_chamada_invalida():
    r = interpretar("<tool_call>\n{nome: errado\n</tool_call>", "q")
    assert r["chamadas"] == [{"id": "q0", "nome": "_invalida", "args": {"_argumentos_invalidos": "{nome: errado"}}]


def test_ida_e_volta_com_corpo():
    for e in EVENTOS:
        if e["papel"] == "agente":
            r = interpretar(corpo(e) + "<|im_end|>", "x")
            assert r["texto"] == e["texto"].strip()
            assert [(c["nome"], c["args"]) for c in r["chamadas"]] == [(c["nome"], c["args"]) for c in e["chamadas"]]


def test_sistema_configuravel(tok):
    assert prompt_sistema(tok, "XYZ").startswith("<|im_start|>system\nXYZ")
    ids, _ = renderizar(EVENTOS[:2], tok, sistema="XYZ")
    assert tok.decode(ids).startswith("<|im_start|>system\nXYZ")
    assert tok.decode(prompt_geracao(EVENTOS[:2], tok, sistema="XYZ")).startswith("<|im_start|>system\nXYZ")
