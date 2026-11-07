"""Tipos do sistema de pedidos simulado. Dinheiro sempre em centavos (int)."""
from dataclasses import asdict, dataclass, field
from datetime import datetime

STATUS = ("recebido", "em_preparo", "a_caminho", "entregue", "cancelado_restaurante", "cancelado_cliente")


@dataclass(frozen=True)
class Item:
    id: str
    nome: str
    preco: int


@dataclass
class Pedido:
    id: str
    cliente_id: str
    restaurante: str
    itens: list[Item]
    taxa: int
    status: str
    feito_em: datetime
    previsto_em: datetime
    entregue_em: datetime | None = None
    estornado: bool = False

    @property
    def total(self) -> int:
        return sum(i.preco for i in self.itens) + self.taxa


@dataclass
class Cenario:
    id: str
    semente: int
    tipo: str
    cliente_id: str
    nome: str
    agora: datetime
    pedidos: list[Pedido]
    pedido_alvo: str | None
    itens_problema: dict[str, str]  # id do item -> "faltando" | "errado" | "estragado"
    estilo: str
    pedido_de_outro: str | None = None  # id que o cliente cita no tipo pedido_de_outro

    def alvo(self) -> Pedido | None:
        return next((p for p in self.pedidos if p.id == self.pedido_alvo), None)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["agora"] = self.agora.isoformat()
        for p in d["pedidos"]:
            for k in ("feito_em", "previsto_em", "entregue_em"):
                p[k] = p[k] and p[k].isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Cenario":
        d = dict(d)
        d["agora"] = datetime.fromisoformat(d["agora"])
        pedidos = []
        for p in d["pedidos"]:
            p = dict(p)
            for k in ("feito_em", "previsto_em", "entregue_em"):
                p[k] = p[k] and datetime.fromisoformat(p[k])
            p["itens"] = [Item(**i) for i in p["itens"]]
            pedidos.append(Pedido(**p))
        d["pedidos"] = pedidos
        return cls(**d)


@dataclass(frozen=True)
class EstadoFinal:
    reembolsos: frozenset[tuple[str, frozenset[str]]] = field(default_factory=frozenset)  # {"todos"} = reembolso total
    cupons: frozenset[tuple[str, int]] = field(default_factory=frozenset)
    cancelamentos: frozenset[str] = field(default_factory=frozenset)
    transferido: bool = False


def reais(centavos: int) -> str:
    s = f"{centavos / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {s}"
