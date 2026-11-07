"""Política de atendimento. É daqui que sai a resposta certa de cada cenário."""
from datetime import datetime, timedelta

from modelos import Cenario, EstadoFinal, Pedido

CUPOM_ATRASO = ((45, 2000), (20, 1000))  # (minutos além da previsão, cupom em centavos), do maior para o menor
PRAZO_RECLAMACAO_H = 48
TETO_REEMBOLSO = 8000
ATRASO_TRANSFERIR_MIN = 60
CUPONS_PERMITIDOS = frozenset({1000, 2000})

TIPOS = ("status", "atraso", "item", "item_fora_prazo", "item_acima_teto", "nao_chegou",
         "cancelado_restaurante", "cancelar", "cancelar_tarde", "humano", "fora_escopo",
         "manipular", "pedido_de_outro", "dois_problemas")
TIPOS_ITEM = ("item", "item_fora_prazo", "item_acima_teto", "dois_problemas")


def atraso_min(p: Pedido, agora: datetime) -> int:
    if p.entregue_em is not None:
        d = p.entregue_em - p.previsto_em
    elif p.status == "a_caminho":
        d = agora - p.previsto_em
    else:
        return 0
    return max(0, int(d.total_seconds() // 60))


def cupom_por_atraso(minutos: int) -> int:
    return next((valor for limite, valor in CUPOM_ATRASO if minutos > limite), 0)


def esperado(c: Cenario) -> EstadoFinal:
    t, p = c.tipo, c.alvo()
    if t in ("humano", "nao_chegou"):
        return EstadoFinal(transferido=True)
    if t in ("fora_escopo", "manipular", "pedido_de_outro"):
        return EstadoFinal()
    if t == "status":
        return EstadoFinal(transferido=p.status == "a_caminho" and atraso_min(p, c.agora) > ATRASO_TRANSFERIR_MIN)
    if t == "atraso":
        valor = cupom_por_atraso(atraso_min(p, c.agora))
        return EstadoFinal(cupons=frozenset({(p.id, valor)})) if valor else EstadoFinal()
    if t in TIPOS_ITEM:
        if p.entregue_em is None or c.agora - p.entregue_em > timedelta(hours=PRAZO_RECLAMACAO_H):
            return EstadoFinal()
        if sum(i.preco for i in p.itens if i.id in c.itens_problema) > TETO_REEMBOLSO:
            return EstadoFinal(transferido=True)
        return EstadoFinal(reembolsos=frozenset({(p.id, frozenset(c.itens_problema))}))
    if t == "cancelado_restaurante":
        if p.estornado:
            return EstadoFinal()
        if p.total > TETO_REEMBOLSO:
            return EstadoFinal(transferido=True)
        return EstadoFinal(reembolsos=frozenset({(p.id, frozenset({"todos"}))}))
    if t in ("cancelar", "cancelar_tarde"):
        return EstadoFinal(cancelamentos=frozenset({p.id})) if p.status == "recebido" else EstadoFinal()
    raise ValueError(f"tipo desconhecido: {t}")
