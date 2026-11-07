import itertools

import pytest

from conversa import Recusa, contexto, rodar
from fabrica import cenario, entregue_com_atraso, pedido, antes


class AgenteRoteiro:
    def __init__(self, turnos):
        self.turnos = iter(turnos)
        self.entradas = []

    def passo(self, entrada):
        self.entradas.append(entrada)
        t = next(self.turnos)
        if isinstance(t, Exception):
            raise t
        return t


class ClienteRoteiro:
    def __init__(self, falas):
        self.falas = iter(falas)

    def falar(self, texto_agente):
        return next(self.falas, None)


def chamada(nome, args=None, id="t1"):
    return {"texto": "", "chamadas": [{"id": id, "nome": nome, "args": args or {}}]}


def texto(t):
    return {"texto": t, "chamadas": []}


C = cenario("status", [pedido(status="a_caminho", previsto=antes(m=10))])


def test_contexto():
    assert contexto(C) == "Cliente logado: Ana (C1). Agora: 07/11 20:00."


def test_conversa_simples():
    agente = AgenteRoteiro([chamada("rastrear_entrega", {"pedido_id": "P1"}), texto("Está a caminho.")])
    conv = rodar(C, agente, ClienteRoteiro(["cadê meu pedido?"]))
    assert [e["papel"] for e in conv.eventos] == ["contexto", "cliente", "agente", "ferramenta", "agente"]
    assert conv.motivo_fim == "cliente_encerrou"
    assert [e["papel"] for e in agente.entradas[0]] == ["contexto", "cliente"]
    assert agente.entradas[1][0]["resultado"]["status"] == "a_caminho"


def test_transferencia_encerra():
    agente = AgenteRoteiro([chamada("transferir_para_humano", {"motivo": "pedido", "resumo": "quer humano"}),
                            texto("Vou te passar para a equipe."), texto("nunca chega aqui")])
    conv = rodar(cenario("humano", [entregue_com_atraso(0)]), agente, ClienteRoteiro(["quero um humano"] * 5))
    assert conv.motivo_fim == "transferido"
    assert conv.estado.transferido
    assert len(agente.entradas) == 2


def test_limite_de_falas():
    agente = AgenteRoteiro(itertools.repeat(texto("Pode repetir?")))
    conv = rodar(C, agente, ClienteRoteiro(itertools.repeat("e aí?")))
    assert conv.motivo_fim == "limite_turnos"
    assert sum(e["papel"] == "cliente" for e in conv.eventos) == 8


def test_limite_de_ferramentas():
    agente = AgenteRoteiro(chamada("listar_pedidos", id=f"t{i}") for i in itertools.count())
    conv = rodar(C, agente, ClienteRoteiro(["oi"]))
    assert conv.motivo_fim == "limite_ferramentas"
    assert sum(e["papel"] == "ferramenta" for e in conv.eventos) == 6


def test_estado_e_bloqueios_vem_do_sistema():
    c = cenario("atraso", [entregue_com_atraso(30)])
    agente = AgenteRoteiro([chamada("emitir_cupom", {"pedido_id": "P1", "valor": 50}), texto("Não deu.")])
    conv = rodar(c, agente, ClienteRoteiro(["atrasou"]))
    assert len(conv.bloqueios) == 1 and not conv.estado.cupons


def test_abertura_vazia_vira_mensagem_padrao():
    conv = rodar(C, AgenteRoteiro([texto("Oi!")]), ClienteRoteiro([]))
    assert conv.eventos[1] == {"papel": "cliente", "texto": "Oi, preciso de ajuda com um pedido."}


def test_recusa_sobe():
    with pytest.raises(Recusa):
        rodar(C, AgenteRoteiro([Recusa("cyber")]), ClienteRoteiro(["oi"]))
