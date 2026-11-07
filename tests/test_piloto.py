from cenarios import PILOTO, lote
from claude import Uso
from conversa import Recusa
from piloto import relatorio, rodar_lote


class UsoFixo:
    def __init__(self, valor):
        self.valor = valor

    def custo(self):
        return self.valor


class AgenteFalso:
    def __init__(self, erro=None, custo=0.5):
        self.erro, self.uso = erro, Uso("claude-opus-5-5", entrada=int(custo * 250_000))

    def passo(self, entrada):
        if self.erro:
            raise self.erro
        return {"texto": "Posso ajudar?", "chamadas": []}


class ClienteFalso:
    def __init__(self):
        self.uso, self.falou = Uso("claude-haiku-5-5"), False

    def falar(self, texto):
        if self.falou:
            return None
        self.falou = True
        return "oi"


def test_falha_e_registrada_e_o_lote_segue():
    cs = lote(PILOTO, 3)
    regs = rodar_lote(cs, lambda c: (AgenteFalso(RuntimeError("caiu") if c is cs[1] else None), ClienteFalso()),
                      teto_dolares=100, paralelo=2)
    status = {r["cenario"]["id"]: r["status"] for r in regs}
    assert status == {cs[0].id: "ok", cs[1].id: "falha", cs[2].id: "ok"}
    assert "caiu" in next(r["erro"] for r in regs if r["status"] == "falha")


def test_recusa_vira_status_recusada():
    regs = rodar_lote(lote(PILOTO, 1), lambda c: (AgenteFalso(Recusa("refusal")), ClienteFalso()), 100, 1)
    assert regs[0]["status"] == "recusada"


def test_teto_para_de_lancar():
    regs = rodar_lote(lote(PILOTO, 10), lambda c: (AgenteFalso(custo=1.0), ClienteFalso()),
                      teto_dolares=2.5, paralelo=1)
    assert len(regs) == 3
    assert sum(r["custo"] for r in regs) == 3.0


def test_cada_registro_e_entregue_assim_que_termina():
    vistos = []
    regs = rodar_lote(lote(PILOTO, 3), lambda c: (AgenteFalso(), ClienteFalso()), 100, 2, ao_terminar=vistos.append)
    assert vistos == regs and len(vistos) == 3


def test_fabrica_que_falha_vira_falha():
    def fabrica(c):
        raise OSError("sem prompt")
    regs = rodar_lote(lote(PILOTO, 2), fabrica, 100, 1)
    assert [r["status"] for r in regs] == ["falha", "falha"]
    assert relatorio(regs).startswith("conversas: 2 (ok 0, recusadas 0, falhas 2)")


def test_estado_ida_e_volta():
    from modelos import EstadoFinal
    from piloto import estado_de_dict, estado_dict
    e = EstadoFinal(reembolsos=frozenset({("P1", frozenset({"i1", "i2"}))}), cupons=frozenset({("P2", 1000)}),
                    cancelamentos=frozenset({"P3"}), transferido=True)
    assert estado_de_dict(estado_dict(e)) == e


def test_relatorio_do_professor_aberto():
    class AgenteAberto(AgenteFalso):
        def __init__(self):
            super().__init__()
            self.uso = Uso("@cf/deepseek-ai/deepseek-v4.1-flash-1017", entrada=20_000)  # US$ 0,006 por conversa

    regs = rodar_lote(lote(PILOTO, 2), lambda c: (AgenteAberto(), ClienteFalso()), 100, 1)
    texto = relatorio(regs)
    assert "deepseek" in texto and "Sonnet" not in texto
    assert "estimativa para 2.000 conversas: US$ 12 (medido, @cf/deepseek-ai/deepseek-v4.1-flash-1017)" in texto


def test_aproveitaveis_exigem_fim_de_verdade():
    from piloto import aproveitaveis
    regs = rodar_lote(lote(PILOTO, 2), lambda c: (AgenteFalso(), ClienteFalso()), 100, 1)
    regs[1]["motivo_fim"] = "limite_turnos"
    assert [r["cenario"]["id"] for r in aproveitaveis(regs)] == [regs[0]["cenario"]["id"]]
    assert "aproveitáveis para treino: 1/2" in relatorio(regs)
    assert "limite_turnos 1" in relatorio(regs)


def test_relatorio():
    regs = rodar_lote(lote(PILOTO, 2), lambda c: (AgenteFalso(), ClienteFalso()), 100, 1)
    texto = relatorio(regs)
    assert "conversas: 2 (ok 2, recusadas 0, falhas 0)" in texto
    assert "acerto do professor: " in texto and "por tipo:" in texto
    assert "1.500 conversas" in texto and "Sonnet 5.5" in texto
