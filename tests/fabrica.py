"""Construtores curtos para os testes montarem cenários à mão."""
from datetime import datetime, timedelta

from modelos import Cenario, Item, Pedido

AGORA = datetime(2026, 11, 7, 20, 0)


def antes(h=0, m=0):
    return AGORA - timedelta(hours=h, minutes=m)


def item(id, preco=2000):
    return Item(id, f"prato {id}", preco)


def pedido(id="P1", status="entregue", itens=None, previsto=None, entregue=None,
           cliente_id="C1", taxa=500, estornado=False):
    previsto = previsto or antes(h=1)
    return Pedido(id=id, cliente_id=cliente_id, restaurante="Cantina Teste",
                  itens=itens or [item("i1")], taxa=taxa, status=status,
                  feito_em=previsto - timedelta(minutes=40), previsto_em=previsto,
                  entregue_em=entregue, estornado=estornado)


def entregue_com_atraso(minutos, id="P1", itens=None, ha_h=1):
    """Pedido entregue `ha_h` horas antes de AGORA, `minutos` depois da previsão."""
    entregue = antes(h=ha_h)
    return pedido(id, "entregue", itens, previsto=entregue - timedelta(minutes=minutos), entregue=entregue)


def cenario(tipo, pedidos, alvo="P1", itens_problema=None, pedido_de_outro=None):
    return Cenario(id=f"{tipo}-0", semente=0, tipo=tipo, cliente_id="C1", nome="Ana",
                   agora=AGORA, pedidos=pedidos, pedido_alvo=alvo,
                   itens_problema=itens_problema or {}, estilo="educado",
                   pedido_de_outro=pedido_de_outro)
