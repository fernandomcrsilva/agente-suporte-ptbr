"""Sistema de pedidos simulado. As ferramentas valem só para o cliente logado e aplicam os limites rígidos."""
from modelos import Cenario, EstadoFinal, reais
from politica import CUPONS_PERMITIDOS, TETO_REEMBOLSO, atraso_min

HORA = "%d/%m %H:%M"
NAO_ENCONTRADO = {"erro": "pedido não encontrado"}

_ID = {"type": "string", "description": "ID do pedido, como aparece em listar_pedidos"}
# nome, descrição para o professor, descrição curta para o aluno, propriedades
_FERRAMENTAS = [
    ("listar_pedidos",
     "Lista os pedidos recentes do cliente logado, com status e total.",
     "Pedidos recentes do cliente.", {}),
    ("detalhar_pedido",
     "Mostra itens (com item_id e preço), taxa de entrega, total, horários e status de um pedido do cliente.",
     "Itens, valores, horários e status de um pedido.", {"pedido_id": _ID}),
    ("rastrear_entrega",
     "Mostra a situação da entrega: status, horário previsto, horário em que foi entregue, minutos de atraso "
     "em relação à previsão e o horário de agora.",
     "Status, previsão, entrega e atraso de um pedido.", {"pedido_id": _ID}),
    ("reembolsar",
     "Reembolsa itens de um pedido. O valor é calculado pelo sistema a partir dos itens. Use itens=[\"todos\"] "
     "para o reembolso total (itens e taxa). Recusa reembolsos acima do teto e pedidos que já receberam compensação.",
     "Reembolsa itens (ou [\"todos\"]) de um pedido.",
     {"pedido_id": _ID,
      "itens": {"type": "array", "items": {"type": "string"}, "description": "item_id de cada item, ou [\"todos\"]"},
      "motivo": {"type": "string"}}),
    ("emitir_cupom",
     "Emite um cupom de desconto para o cliente, ligado a um pedido. Só aceita os valores da política, em reais.",
     "Emite um cupom (em reais) ligado a um pedido.",
     {"pedido_id": _ID, "valor": {"type": "number", "description": "valor do cupom em reais"}}),
    ("cancelar_pedido",
     "Cancela um pedido. Só funciona se o restaurante ainda não começou o preparo.",
     "Cancela um pedido que ainda não entrou em preparo.", {"pedido_id": _ID}),
    ("transferir_para_humano",
     "Transfere o atendimento para uma pessoa da equipe. Encerra o atendimento automático.",
     "Passa o atendimento para uma pessoa.",
     {"motivo": {"type": "string"}, "resumo": {"type": "string", "description": "resumo do caso para a equipe"}}),
]
NOMES = tuple(f[0] for f in _FERRAMENTAS)


def _schema(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def ferramentas_anthropic() -> list[dict]:
    return [{"name": n, "description": d, "input_schema": _schema(p), "strict": True} for n, d, _, p in _FERRAMENTAS]


def ferramentas_qwen() -> list[dict]:
    return [{"type": "function", "function": {"name": n, "description": curta, "parameters": _schema(p)}}
            for n, _, curta, p in _FERRAMENTAS]


def _texto(v, nome):
    if not isinstance(v, str):
        raise ValueError(f"{nome} precisa ser texto")
    return v


def _hora(dt):
    return dt and dt.strftime(HORA)


class Sistema:
    def __init__(self, c: Cenario):
        self.c = c
        self.pedidos = {p.id: p for p in c.pedidos if p.cliente_id == c.cliente_id}
        self.status = {i: p.status for i, p in self.pedidos.items()}
        self.bloqueios: list[dict] = []
        self.transferido = False
        self.reembolsos: dict[str, frozenset[str]] = {}
        self.cupons: dict[str, int] = {}
        self.cancelamentos: set[str] = set()

    def executar(self, nome: str, args: dict) -> dict:
        if nome not in NOMES:
            return {"erro": f"ferramenta desconhecida: {nome}"}
        try:
            return getattr(self, nome)(**args)
        except (KeyError, TypeError, ValueError) as e:
            return {"erro": f"argumentos inválidos: {e}"}

    def estado_final(self) -> EstadoFinal:
        return EstadoFinal(reembolsos=frozenset(self.reembolsos.items()), cupons=frozenset(self.cupons.items()),
                           cancelamentos=frozenset(self.cancelamentos), transferido=self.transferido)

    def _bloquear(self, ferramenta, args, motivo):
        self.bloqueios.append({"ferramenta": ferramenta, "args": args, "motivo": motivo})
        return {"erro": motivo}

    def _compensado(self, pedido_id):
        return pedido_id in self.reembolsos or pedido_id in self.cupons

    def listar_pedidos(self):
        return {"pedidos": [{"pedido_id": p.id, "restaurante": p.restaurante, "status": self.status[p.id],
                             "total": reais(p.total), "feito_em": _hora(p.feito_em)} for p in self.pedidos.values()]}

    def detalhar_pedido(self, pedido_id):
        p = self.pedidos.get(_texto(pedido_id, "pedido_id"))
        if p is None:
            return NAO_ENCONTRADO
        return {"pedido_id": p.id, "restaurante": p.restaurante, "status": self.status[p.id],
                "itens": [{"item_id": i.id, "nome": i.nome, "preco": reais(i.preco)} for i in p.itens],
                "taxa": reais(p.taxa), "total": reais(p.total), "feito_em": _hora(p.feito_em),
                "previsto_em": _hora(p.previsto_em), "entregue_em": _hora(p.entregue_em), "estornado": p.estornado}

    def rastrear_entrega(self, pedido_id):
        p = self.pedidos.get(_texto(pedido_id, "pedido_id"))
        if p is None:
            return NAO_ENCONTRADO
        saiu = self.status[p.id] in ("a_caminho", "entregue")
        return {"pedido_id": p.id, "status": self.status[p.id], "previsto_em": _hora(p.previsto_em),
                "entregue_em": _hora(p.entregue_em), "atraso_minutos": atraso_min(p, self.c.agora) if saiu else None,
                "agora": _hora(self.c.agora)}

    def reembolsar(self, pedido_id, itens, motivo):
        args = {"pedido_id": pedido_id, "itens": itens, "motivo": motivo}
        p = self.pedidos.get(_texto(pedido_id, "pedido_id"))
        _texto(motivo, "motivo")
        if not isinstance(itens, list) or not itens or not all(isinstance(i, str) for i in itens):
            raise ValueError("itens precisa ser uma lista de item_id")
        if p is None:
            return NAO_ENCONTRADO
        if itens == ["todos"]:
            valor = p.total
        else:
            precos = {i.id: i.preco for i in p.itens}
            faltam = [i for i in itens if i not in precos]
            if faltam:
                return {"erro": f"item não existe no pedido: {', '.join(faltam)}"}
            valor = sum(precos[i] for i in set(itens))
        if self._compensado(p.id):
            return self._bloquear("reembolsar", args, "este pedido já recebeu uma compensação")
        if valor > TETO_REEMBOLSO:
            return self._bloquear("reembolsar", args, "reembolso acima do teto de R$ 80; transfira para um humano")
        self.reembolsos[p.id] = frozenset(itens)
        return {"ok": True, "valor": reais(valor)}

    def emitir_cupom(self, pedido_id, valor):
        args = {"pedido_id": pedido_id, "valor": valor}
        p = self.pedidos.get(_texto(pedido_id, "pedido_id"))
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError("valor precisa ser um número em reais")
        if p is None:
            return NAO_ENCONTRADO
        centavos = round(valor * 100)
        if centavos not in CUPONS_PERMITIDOS:
            return self._bloquear("emitir_cupom", args, "valor de cupom fora da política (R$ 10 ou R$ 20)")
        if self._compensado(p.id):
            return self._bloquear("emitir_cupom", args, "este pedido já recebeu uma compensação")
        self.cupons[p.id] = centavos
        return {"ok": True, "cupom": reais(centavos)}

    def cancelar_pedido(self, pedido_id):
        p = self.pedidos.get(_texto(pedido_id, "pedido_id"))
        if p is None:
            return NAO_ENCONTRADO
        if self.status[p.id] != "recebido":
            return self._bloquear("cancelar_pedido", {"pedido_id": pedido_id},
                                  "o pedido não pode mais ser cancelado: o restaurante já começou o preparo")
        self.status[p.id] = "cancelado_cliente"
        self.cancelamentos.add(p.id)
        return {"ok": True}

    def transferir_para_humano(self, motivo, resumo):
        _texto(motivo, "motivo"), _texto(resumo, "resumo")
        self.transferido = True
        return {"ok": True, "protocolo": f"H-{self.c.semente}"}
