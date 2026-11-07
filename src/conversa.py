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


def rodar(c: Cenario, agente: Agente, cliente: Cliente, max_falas: int = 8,
          max_rodadas_ferramenta: int = 6) -> Conversa:
    sistema = Sistema(c)
    fala = {"papel": "cliente", "texto": cliente.falar(None)}
    eventos = [{"papel": "contexto", "texto": contexto(c)}, fala]
    entrada, falas, rodadas = list(eventos), 1, 0

    def fim(motivo):
        return Conversa(c, eventos, sistema.estado_final(), sistema.bloqueios, motivo)

    while True:
        turno = agente.passo(entrada)
        eventos.append({"papel": "agente", "texto": turno["texto"], "chamadas": turno["chamadas"]})
        if turno["chamadas"]:
            entrada = [{"papel": "ferramenta", "id": ch["id"], "nome": ch["nome"],
                        "resultado": sistema.executar(ch["nome"], ch["args"])} for ch in turno["chamadas"]]
            eventos += entrada
            rodadas += 1
            if sistema.transferido:
                # ponytail: um passo final para se despedir; chamadas nesse passo não são executadas
                final = agente.passo(entrada)
                eventos.append({"papel": "agente", "texto": final["texto"], "chamadas": final["chamadas"]})
                return fim("transferido")
            if rodadas >= max_rodadas_ferramenta:
                return fim("limite_ferramentas")
            continue
        rodadas = 0
        if falas >= max_falas:
            return fim("limite_turnos")
        texto = cliente.falar(turno["texto"])
        if texto is None:
            return fim("cliente_encerrou")
        falas += 1
        entrada = [{"papel": "cliente", "texto": texto}]
        eventos += entrada
