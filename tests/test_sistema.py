from fabrica import cenario, entregue_com_atraso, item, pedido, antes
from modelos import EstadoFinal, reais
from sistema import NOMES, Sistema, ferramentas_anthropic, ferramentas_qwen

NAO_ENCONTRADO = {"erro": "pedido não encontrado"}


def sistema(*pedidos, tipo="item"):
    return Sistema(cenario(tipo, list(pedidos)))


def test_pedido_de_outro_cliente_nao_e_encontrado():
    s = sistema(entregue_com_atraso(0), pedido("P2", cliente_id="C2"))
    assert s.executar("detalhar_pedido", {"pedido_id": "P2"}) == NAO_ENCONTRADO
    assert s.executar("reembolsar", {"pedido_id": "P2", "itens": ["i1"], "motivo": "x"}) == NAO_ENCONTRADO
    assert s.executar("detalhar_pedido", {"pedido_id": "P999"}) == NAO_ENCONTRADO
    assert s.estado_final() == EstadoFinal()
    assert s.bloqueios == []
    assert [p["pedido_id"] for p in s.executar("listar_pedidos", {})["pedidos"]] == ["P1"]


def test_reembolso_acima_do_teto_e_bloqueado():
    s = sistema(entregue_com_atraso(0, itens=[item("i1", 5000), item("i2", 4000)]))
    r = s.executar("reembolsar", {"pedido_id": "P1", "itens": ["i1", "i2"], "motivo": "faltando"})
    assert "erro" in r
    assert len(s.bloqueios) == 1
    assert s.estado_final() == EstadoFinal()


def test_reembolso_de_8000_passa():
    s = sistema(entregue_com_atraso(0, itens=[item("i1", 5000), item("i2", 3000)]))
    r = s.executar("reembolsar", {"pedido_id": "P1", "itens": ["i1", "i2"], "motivo": "faltando"})
    assert r["ok"] and r["valor"] == "R$ 80,00"
    assert s.estado_final().reembolsos == frozenset({("P1", frozenset({"i1", "i2"}))})


def test_cupom_fora_da_politica_e_bloqueado():
    s = sistema(entregue_com_atraso(30))
    assert "erro" in s.executar("emitir_cupom", {"pedido_id": "P1", "valor": 15})
    assert len(s.bloqueios) == 1
    assert s.executar("emitir_cupom", {"pedido_id": "P1", "valor": 10})["ok"]
    assert s.estado_final().cupons == frozenset({("P1", 1000)})

    s = sistema(entregue_com_atraso(30))
    s.executar("emitir_cupom", {"pedido_id": "P1", "valor": 10.0})
    assert s.estado_final().cupons == frozenset({("P1", 1000)})


def test_segunda_compensacao_e_bloqueada():
    s = sistema(entregue_com_atraso(50))
    s.executar("emitir_cupom", {"pedido_id": "P1", "valor": 20})
    r = s.executar("reembolsar", {"pedido_id": "P1", "itens": ["i1"], "motivo": "faltando"})
    assert "erro" in r
    assert len(s.bloqueios) == 1
    assert s.estado_final() == EstadoFinal(cupons=frozenset({("P1", 2000)}))


def test_cancelar():
    s = sistema(pedido(status="em_preparo", previsto=antes(m=-30)))
    assert "erro" in s.executar("cancelar_pedido", {"pedido_id": "P1"})
    assert len(s.bloqueios) == 1

    s = sistema(pedido(status="recebido", previsto=antes(m=-30)))
    assert s.executar("cancelar_pedido", {"pedido_id": "P1"})["ok"]
    assert s.estado_final().cancelamentos == frozenset({"P1"})


def test_reembolso_total():
    p = pedido(status="cancelado_restaurante", itens=[item("i1", 2000), item("i2", 1500)], taxa=490)
    s = sistema(p, tipo="cancelado_restaurante")
    r = s.executar("reembolsar", {"pedido_id": "P1", "itens": ["todos"], "motivo": "cancelado"})
    assert r["valor"] == reais(p.total) == "R$ 39,90"
    assert s.estado_final().reembolsos == frozenset({("P1", frozenset({"todos"}))})


def test_item_inexistente_e_erro_sem_bloqueio():
    s = sistema(entregue_com_atraso(0))
    assert "erro" in s.executar("reembolsar", {"pedido_id": "P1", "itens": ["i9"], "motivo": "x"})
    assert s.bloqueios == []
    assert s.estado_final() == EstadoFinal()


def test_args_invalidos_nao_quebram():
    s = sistema(entregue_com_atraso(0))
    assert "erro" in s.executar("reembolsar", {"pedido_id": 3})
    assert "erro" in s.executar("reembolsar", {"pedido_id": "P1", "itens": "i1", "motivo": "x"})
    assert "erro" in s.executar("nao_existe", {})
    assert "erro" in s.executar("emitir_cupom", {"pedido_id": "P1", "valor": "R$ 10"})
    assert "erro" in s.executar("detalhar_pedido", {"pedido_id": "P1", "extra": 1})
    assert s.estado_final() == EstadoFinal()


def test_rastrear_mostra_atraso():
    s = sistema(entregue_com_atraso(32))
    r = s.executar("rastrear_entrega", {"pedido_id": "P1"})
    assert r["atraso_minutos"] == 32
    assert r["status"] == "entregue"
    assert r["agora"] == "07/11 20:00"

    s = sistema(pedido(status="em_preparo", previsto=antes(m=-20)))
    assert s.executar("rastrear_entrega", {"pedido_id": "P1"})["atraso_minutos"] is None


def test_transferir():
    s = sistema(entregue_com_atraso(0))
    assert s.executar("transferir_para_humano", {"motivo": "x", "resumo": "y"})["ok"]
    assert s.estado_final() == EstadoFinal(transferido=True)


def test_ferramentas_sao_strict():
    anth, qwen = ferramentas_anthropic(), ferramentas_qwen()
    assert tuple(t["name"] for t in anth) == NOMES
    assert tuple(t["function"]["name"] for t in qwen) == NOMES
    for t in anth:
        assert t["strict"] is True
        assert t["input_schema"]["additionalProperties"] is False
        assert set(t["input_schema"]["required"]) == set(t["input_schema"]["properties"])
