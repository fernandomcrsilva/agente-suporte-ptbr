from collections import Counter

from cenarios import TESTE, carregar, fatos_cliente, gerar, lote, objetivo_cliente, salvar
from modelos import EstadoFinal
from politica import TIPOS, esperado

SEMENTES = range(50)


def esperados(tipo):
    return [esperado(gerar(s, tipo)) for s in SEMENTES]


def test_mesma_semente_mesmo_cenario():
    assert gerar(7, "atraso").to_dict() == gerar(7, "atraso").to_dict()
    assert gerar(7, "atraso").to_dict() != gerar(8, "atraso").to_dict()


def test_lote_cobre_os_tipos_por_igual():
    cs = lote(TESTE, 28)
    assert Counter(c.tipo for c in cs) == {t: 2 for t in TIPOS}
    assert cs[0].semente == TESTE and cs[0].id == f"{cs[0].tipo}-{TESTE}"


def test_cada_tipo_cai_no_ramo_certo():
    assert all(e == EstadoFinal() for e in esperados("item_fora_prazo"))
    for tipo in ("item_acima_teto", "humano", "nao_chegou"):
        assert all(e.transferido for e in esperados(tipo)), tipo
    assert all(e.reembolsos and not e.transferido for e in esperados("item"))
    assert all(e.cancelamentos for e in esperados("cancelar"))
    assert not any(e.cancelamentos for e in esperados("cancelar_tarde"))
    for s in SEMENTES:
        c = gerar(s, "pedido_de_outro")
        assert c.pedido_de_outro and c.pedido_de_outro not in [p.id for p in c.pedidos]
    cupons = Counter(next(iter(e.cupons))[1] if e.cupons else 0 for e in esperados("atraso"))
    assert cupons[0] and cupons[1000] and cupons[2000]
    assert any(e.transferido for e in esperados("status")) and not all(e.transferido for e in esperados("status"))


def test_cenario_valido():
    for c in lote(0, 140):
        if c.tipo != "pedido_de_outro":
            alvo = c.alvo()
            assert alvo is not None
            assert set(c.itens_problema) <= {i.id for i in alvo.itens}
        assert len({p.id for p in c.pedidos}) == len(c.pedidos)
        assert all(p.cliente_id == c.cliente_id for p in c.pedidos)


def test_objetivo_e_fatos_para_todo_tipo():
    for tipo in TIPOS:
        c = gerar(3, tipo)
        assert objetivo_cliente(c).strip() and fatos_cliente(c).strip(), tipo


def test_salvar_e_carregar_ida_e_volta(tmp_path):
    cs = lote(0, 14)
    salvar(cs, tmp_path / "c.jsonl")
    assert [c.to_dict() for c in carregar(tmp_path / "c.jsonl")] == [c.to_dict() for c in cs]
