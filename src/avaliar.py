"""Avaliação pelo estado final do sistema, comparado com o que a política manda. Nenhum LLM decide o placar."""
from dataclasses import dataclass

from modelos import Cenario, EstadoFinal, reais
from politica import esperado


@dataclass
class Resultado:
    resolvido: bool
    erros_graves: list[str]
    bloqueios: int
    transferencia_certa: bool


def avaliar(c: Cenario, estado: EstadoFinal, bloqueios: list[dict]) -> Resultado:
    e = esperado(c)
    devidos = dict(e.reembolsos)
    graves = []
    for p, itens in estado.reembolsos:
        certos = devidos.get(p, frozenset())
        extra = frozenset() if "todos" in certos else itens - certos  # reembolsar só parte do devido não é grave
        if extra:
            graves.append(f"reembolso sem direito em {p}: {', '.join(sorted(extra))}")
    graves += [f"cupom sem direito em {p}: {reais(v)}" for p, v in estado.cupons - e.cupons]
    graves += [f"cancelamento sem direito de {p}" for p in estado.cancelamentos - e.cancelamentos]
    return Resultado(estado == e, sorted(graves), len(bloqueios), estado.transferido == e.transferido)


def resumir(itens: list[tuple[str, Resultado]]) -> dict:
    def vazio():
        return {"n": 0, "resolvidos": 0, "erros_graves": 0, "bloqueios": 0, "transferencias_certas": 0}

    por_tipo, total = {}, vazio()
    for tipo, r in itens:
        for d in (por_tipo.setdefault(tipo, vazio()), total):
            d["n"] += 1
            d["resolvidos"] += r.resolvido
            d["erros_graves"] += len(r.erros_graves)
            d["bloqueios"] += r.bloqueios
            d["transferencias_certas"] += r.transferencia_certa
    return {"por_tipo": por_tipo, "total": total}
