"""Loop de conversa: liga um agente qualquer a um cliente simulado e ao sistema de pedidos."""
from dataclasses import dataclass
from typing import Protocol

from modelos import Cenario, EstadoFinal
from sistema import Sistema


class Recusa(Exception):
    """O modelo recusou ou parou no meio. A conversa é descartada."""


class Agente(Protocol):
    def passo(self, entrada: list[dict]) -> dict: ...  # {"texto": str, "chamadas": [{"id", "nome", "args"}]}


class Cliente(Protocol):
    def falar(self, texto_agente: str | None) -> str | None: ...  # None na entrada: abertura; na saída: encerrou


@dataclass
class Conversa:
    cenario: Cenario
    eventos: list[dict]
    estado: EstadoFinal
    bloqueios: list[dict]
    motivo_fim: str  # cliente_encerrou | transferido | limite_turnos | limite_ferramentas


def contexto(c: Cenario) -> str:
    return f"Cliente logado: {c.nome} ({c.cliente_id}). Agora: {c.agora.strftime('%d/%m %H:%M')}."


class Sessao:
    """Uma conversa avançada uma fala do cliente por vez: o loop, a demo (quem escreve é uma pessoa) e o teste."""

    def __init__(self, c: Cenario, agente: Agente, max_rodadas_ferramenta: int = 6):
        self.c, self.agente, self.max_rodadas = c, agente, max_rodadas_ferramenta
        self.sistema = Sistema(c)
        self.eventos: list[dict] = []
        self.motivo_fim: str | None = None  # transferido | limite_ferramentas (ou o que quem usa definir)

    def responder(self, texto_cliente: str) -> str:
        """Entrega a fala do cliente e roda o agente até ele responder sem ferramenta. Devolve o que ele disse."""
        if self.motivo_fim:
            raise RuntimeError("atendimento encerrado")
        entrada = [{"papel": "cliente", "texto": texto_cliente}]
        if not self.eventos:
            entrada.insert(0, {"papel": "contexto", "texto": contexto(self.c)})
        self.eventos += entrada
        for _ in range(self.max_rodadas):
            turno = self.agente.passo(entrada)
            self.eventos.append({"papel": "agente", "texto": turno["texto"], "chamadas": turno["chamadas"]})
            if not turno["chamadas"]:
                return turno["texto"]
            entrada = [{"papel": "ferramenta", "id": ch["id"], "nome": ch["nome"],
                        "resultado": self.sistema.executar(ch["nome"], ch["args"])} for ch in turno["chamadas"]]
            self.eventos += entrada
            if self.sistema.transferido:
                self.motivo_fim = "transferido"  # antes da despedida: se ela falhar, a sessão já está travada
                # ponytail: um passo final para se despedir; chamadas nesse passo não são executadas
                final = self.agente.passo(entrada)
                self.eventos.append({"papel": "agente", "texto": final["texto"], "chamadas": final["chamadas"]})
                return final["texto"]
        self.motivo_fim = "limite_ferramentas"
        return ""

    def conversa(self, motivo: str) -> Conversa:
        return Conversa(self.c, self.eventos, self.sistema.estado_final(), self.sistema.bloqueios, motivo)


def rodar(c: Cenario, agente: Agente, cliente: Cliente, max_falas: int = 8,
          max_rodadas_ferramenta: int = 6) -> Conversa:
    s = Sessao(c, agente, max_rodadas_ferramenta)
    # Se o cliente simulado já encerrar na abertura, a conversa começa com um pedido genérico de ajuda.
    texto = cliente.falar(None) or "Oi, preciso de ajuda com um pedido."
    falas = 1
    while True:
        resposta = s.responder(texto)
        if s.motivo_fim:
            return s.conversa(s.motivo_fim)
        if falas >= max_falas:
            return s.conversa("limite_turnos")
        texto = cliente.falar(resposta)
        if texto is None:
            return s.conversa("cliente_encerrou")
        falas += 1
