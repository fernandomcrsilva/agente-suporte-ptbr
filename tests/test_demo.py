import json

from cenarios import DEMO
from demo import CASOS, aviso_fim, conferencia, enviar, novo_atendimento, painel
from politica import TIPOS
from test_aluno import ModeloFalso, tok  # noqa: F401 (fixture)


def chamada(nome, args):
    return f'<tool_call>\n{json.dumps({"name": nome, "arguments": args}, ensure_ascii=False)}\n</tool_call><|im_end|>'


def test_casos_usam_sementes_da_demo():
    assert len(CASOS) == 7
    for semente, tipo in CASOS.values():
        assert DEMO <= semente < DEMO + 1000 and tipo in TIPOS


def test_mensagem_vazia_nao_chama_o_modelo(tok):
    m = ModeloFalso(tok, [])
    s = novo_atendimento("Pedido chegou atrasado", m)
    assert enviar(s, "   ") == ("", 0.0)
    assert m.prompts == [] and s.eventos == []


def test_resposta_vazia_vira_aviso(tok):
    s = novo_atendimento("Pedido chegou atrasado", ModeloFalso(tok, ["<|im_end|>"]))
    assert enviar(s, "oi")[0] == "(o atendente não escreveu nada)"


class Quebrado:
    def __init__(self, tok, erro):
        self.tok, self.erro = tok, erro

    def gerar(self, ids):
        raise self.erro


def test_contexto_cheio_encerra(tok):
    from aluno import ContextoCheio

    s = novo_atendimento("Pedido chegou atrasado", Quebrado(tok, ContextoCheio("conversa maior que o contexto")))
    enviar(s, "oi")
    assert s.motivo_fim == "contexto_cheio" and "contexto" in aviso_fim(s.motivo_fim)


def test_erro_da_gpu_encerra_com_a_mensagem(tok):
    s = novo_atendimento("Pedido chegou atrasado", Quebrado(tok, RuntimeError("You have exceeded your free ZeroGPU quota")))
    resposta, _ = enviar(s, "oi")
    assert s.motivo_fim == "erro"
    assert "ZeroGPU quota" in resposta and "login" in resposta


def _reembolso_certo(tok):
    s = novo_atendimento("Item faltando ou errado", ModeloFalso(tok, []))
    itens = sorted(s.c.itens_problema)
    s.agente.modelo = ModeloFalso(tok, [
        chamada("reembolsar", {"pedido_id": s.c.pedido_alvo, "itens": itens, "motivo": "item com problema"}),
        "Pronto, reembolsei.<|im_end|>"])
    resposta, segundos = enviar(s, "Veio faltando coisa no meu pedido.")
    assert resposta == "Pronto, reembolsei." and segundos >= 0
    return s, itens


def test_painel_mostra_ferramenta_e_estado(tok):
    s, itens = _reembolso_certo(tok)
    texto = painel(s)
    nome = next(i.nome for i in s.c.alvo().itens if i.id == itens[0])
    assert "reembolsar" in texto and nome in texto and "R$" in texto


def test_conferencia_diz_se_resolveu(tok):
    s, _ = _reembolso_certo(tok)
    assert "Resolvido certo: sim" in conferencia(s)
    s2 = novo_atendimento("Item faltando ou errado", ModeloFalso(tok, ["Não posso ajudar.<|im_end|>"]))
    enviar(s2, "Veio faltando coisa no meu pedido.")
    assert "Resolvido certo: não" in conferencia(s2)


def test_demo_trava_depois_de_transferir(tok):
    s = novo_atendimento("Diz que não chegou, mas o rastreio diz entregue", ModeloFalso(tok, [
        chamada("transferir_para_humano", {"motivo": "não chegou", "resumo": "cliente diz que não recebeu"}),
        "Já te passei para um colega.<|im_end|>"]))
    assert enviar(s, "Meu pedido não chegou!")[0] == "Já te passei para um colega."
    assert s.motivo_fim == "transferido" and "pessoa" in aviso_fim(s.motivo_fim)
