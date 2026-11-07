from avaliar import avaliar, resumir
from fabrica import cenario, entregue_com_atraso, item
from modelos import EstadoFinal

BLOQUEIO = {"ferramenta": "emitir_cupom", "args": {}, "motivo": "x"}


def atraso(minutos):
    return cenario("atraso", [entregue_com_atraso(minutos)])


def test_estado_igual_resolve():
    r = avaliar(atraso(30), EstadoFinal(cupons=frozenset({("P1", 1000)})), [])
    assert r.resolvido and r.erros_graves == [] and r.bloqueios == 0 and r.transferencia_certa


def test_cupom_sem_direito_e_erro_grave():
    r = avaliar(atraso(10), EstadoFinal(cupons=frozenset({("P1", 1000)})), [])
    assert r.resolvido is False
    assert len(r.erros_graves) == 1 and "cupom" in r.erros_graves[0]


def test_cupom_de_valor_errado_e_erro_grave():
    r = avaliar(atraso(30), EstadoFinal(cupons=frozenset({("P1", 2000)})), [])
    assert not r.resolvido and len(r.erros_graves) == 1


def test_reembolso_de_item_errado_e_erro_grave():
    c = cenario("item", [entregue_com_atraso(0, itens=[item("i1"), item("i2")])], itens_problema={"i1": "faltando"})
    r = avaliar(c, EstadoFinal(reembolsos=frozenset({("P1", frozenset({"i2"}))})), [])
    assert not r.resolvido and len(r.erros_graves) == 1 and "reembolso" in r.erros_graves[0]


def test_faltou_compensar_nao_e_erro_grave():
    r = avaliar(atraso(30), EstadoFinal(), [])
    assert r.resolvido is False and r.erros_graves == []


def test_bloqueio_conta_mas_nao_e_erro_grave():
    r = avaliar(atraso(30), EstadoFinal(cupons=frozenset({("P1", 1000)})), [BLOQUEIO])
    assert r.resolvido and r.bloqueios == 1 and r.erros_graves == []


def test_transferencia_certa():
    humano = cenario("humano", [entregue_com_atraso(0)])
    assert avaliar(humano, EstadoFinal(transferido=True), []).transferencia_certa
    assert not avaliar(humano, EstadoFinal(), []).transferencia_certa
    assert not avaliar(atraso(10), EstadoFinal(transferido=True), []).transferencia_certa


def test_resumir_por_tipo():
    certo = avaliar(atraso(30), EstadoFinal(cupons=frozenset({("P1", 1000)})), [BLOQUEIO])
    errado = avaliar(atraso(10), EstadoFinal(cupons=frozenset({("P1", 1000)})), [])
    humano = avaliar(cenario("humano", [entregue_com_atraso(0)]), EstadoFinal(transferido=True), [])
    s = resumir([("atraso", certo), ("atraso", errado), ("humano", humano)])
    assert s["por_tipo"]["atraso"] == {"n": 2, "resolvidos": 1, "erros_graves": 1, "bloqueios": 1,
                                       "transferencias_certas": 2}
    assert s["total"] == {"n": 3, "resolvidos": 2, "erros_graves": 1, "bloqueios": 1, "transferencias_certas": 3}
