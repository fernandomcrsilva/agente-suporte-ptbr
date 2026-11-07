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


def test_relatorio():
    regs = rodar_lote(lote(PILOTO, 2), lambda c: (AgenteFalso(), ClienteFalso()), 100, 1)
    texto = relatorio(regs)
    assert "conversas: 2 (ok 2, recusadas 0, falhas 0)" in texto
    assert "acerto do professor: " in texto and "por tipo:" in texto
    assert "1.500 conversas" in texto and "Sonnet 5.5" in texto
