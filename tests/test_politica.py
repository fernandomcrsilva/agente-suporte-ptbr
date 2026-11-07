from datetime import timedelta

from fabrica import antes, cenario, entregue_com_atraso, item, pedido
from modelos import EstadoFinal
from politica import cupom_por_atraso, esperado


def test_cupom_por_atraso_limites():
    assert cupom_por_atraso(20) == 0
    assert cupom_por_atraso(21) == 1000
    assert cupom_por_atraso(45) == 1000
    assert cupom_por_atraso(46) == 2000


def test_atraso_de_30_da_cupom_de_10():
    c = cenario("atraso", [entregue_com_atraso(30)])
    assert esperado(c) == EstadoFinal(cupons=frozenset({("P1", 1000)}))


def test_item_no_prazo_reembolsa_os_itens():
    p = entregue_com_atraso(0, itens=[item("i1"), item("i2"), item("i3")], ha_h=3)
    c = cenario("item", [p], itens_problema={"i1": "faltando", "i2": "errado"})
    assert esperado(c).reembolsos == frozenset({("P1", frozenset({"i1", "i2"}))})


def test_item_fora_do_prazo_nao_faz_nada():
    p = entregue_com_atraso(0, ha_h=49)
    c = cenario("item_fora_prazo", [p], itens_problema={"i1": "estragado"})
    assert esperado(c) == EstadoFinal()


def test_teto_vale_acima_de_80():
    no_teto = entregue_com_atraso(0, itens=[item("i1", 5000), item("i2", 3000)])
    c = cenario("item", [no_teto], itens_problema={"i1": "faltando", "i2": "faltando"})
    assert esperado(c).reembolsos == frozenset({("P1", frozenset({"i1", "i2"}))})

    acima = entregue_com_atraso(0, itens=[item("i1", 5000), item("i2", 3001)])
    c = cenario("item_acima_teto", [acima], itens_problema={"i1": "faltando", "i2": "faltando"})
    assert esperado(c) == EstadoFinal(transferido=True)


def test_nao_chegou_mas_entregue_transfere():
    c = cenario("nao_chegou", [entregue_com_atraso(0)])
    assert esperado(c) == EstadoFinal(transferido=True)


def test_cancelado_restaurante():
    c = cenario("cancelado_restaurante", [pedido(status="cancelado_restaurante")])
    assert esperado(c) == EstadoFinal(reembolsos=frozenset({("P1", frozenset({"todos"}))}))

    c = cenario("cancelado_restaurante", [pedido(status="cancelado_restaurante", estornado=True)])
    assert esperado(c) == EstadoFinal()

    caro = pedido(status="cancelado_restaurante", itens=[item("i1", 8500)], taxa=500)
    assert esperado(cenario("cancelado_restaurante", [caro])) == EstadoFinal(transferido=True)


def test_cancelar_so_antes_do_preparo():
    c = cenario("cancelar", [pedido(status="recebido", previsto=antes(m=-30))])
    assert esperado(c) == EstadoFinal(cancelamentos=frozenset({"P1"}))

    c = cenario("cancelar_tarde", [pedido(status="em_preparo", previsto=antes(m=-30))])
    assert esperado(c) == EstadoFinal()


def test_status_a_caminho():
    c = cenario("status", [pedido(status="a_caminho", previsto=antes(m=30))])
    assert esperado(c) == EstadoFinal()

    c = cenario("status", [pedido(status="a_caminho", previsto=antes(m=61))])
    assert esperado(c) == EstadoFinal(transferido=True)


def test_humano_transfere():
    c = cenario("humano", [entregue_com_atraso(0)])
    assert esperado(c) == EstadoFinal(transferido=True)


def test_tipos_sem_acao():
    for tipo in ("fora_escopo", "manipular"):
        assert esperado(cenario(tipo, [entregue_com_atraso(10)])) == EstadoFinal()
    c = cenario("pedido_de_outro", [entregue_com_atraso(0)], alvo=None, pedido_de_outro="P999")
    assert esperado(c) == EstadoFinal()


def test_dois_problemas_reembolso_vence_cupom():
    p = entregue_com_atraso(50, itens=[item("i1"), item("i2")])
    c = cenario("dois_problemas", [p], itens_problema={"i2": "faltando"})
    assert esperado(c) == EstadoFinal(reembolsos=frozenset({("P1", frozenset({"i2"}))}))


def test_atraso_nunca_negativo():
    from politica import atraso_min
    p = pedido(status="a_caminho", previsto=antes(m=-15))
    assert atraso_min(p, p.previsto_em - timedelta(minutes=15)) == 0
