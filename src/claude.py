"""Professor (o atendente) e cliente simulado no Claude, com a contagem de custo de cada um."""
import json
from dataclasses import dataclass
from pathlib import Path

from cenarios import EMPRESA, fatos_cliente, objetivo_cliente
from conversa import Recusa
from modelos import Cenario
from sistema import ferramentas_anthropic

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
FRASE_HUMANO = "Nunca peça para falar com um humano."
# US$ por milhão de tokens: entrada, saída, leitura de cache, escrita de cache (5 minutos)
PRECOS = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.10, 0.125),  # ponytail: sem preço de cache do Haiku na tabela; usa o teto
}


@dataclass
class Uso:
    modelo: str
    entrada: int = 0
    saida: int = 0
    cache_leitura: int = 0
    cache_escrita: int = 0

    def somar(self, u) -> None:
        self.entrada += u.input_tokens
        self.saida += u.output_tokens
        self.cache_leitura += u.cache_read_input_tokens or 0
        self.cache_escrita += u.cache_creation_input_tokens or 0

    def custo(self) -> float:
        e, s, cl, ce = PRECOS[self.modelo]
        return (self.entrada * e + self.saida * s + self.cache_leitura * cl + self.cache_escrita * ce) / 1e6


def mensagem_usuario(entrada: list[dict]) -> dict:
    blocos = []
    for e in entrada:
        if e["papel"] == "ferramenta":
            blocos.append({"type": "tool_result", "tool_use_id": e["id"], "is_error": "erro" in e["resultado"],
                           "content": json.dumps(e["resultado"], ensure_ascii=False)})
        else:
            blocos.append({"type": "text", "text": e["texto"]})
    return {"role": "user", "content": blocos}


def _texto(resposta) -> str:
    return "".join(b.text for b in resposta.content if b.type == "text")


class Professor:
    """O atendente. Sem fallback: uma conversa recusada é descartada, para todas virem do mesmo professor."""

    def __init__(self, api, modelo: str = "claude-opus-5-5", effort: str = "low"):
        self.api, self.modelo, self.effort = api, modelo, effort
        self.sistema = (PROMPTS / "professor.md").read_text().replace("{EMPRESA}", EMPRESA)
        self.mensagens: list[dict] = []
        self.uso = Uso(modelo)

    def passo(self, entrada: list[dict]) -> dict:
        self.mensagens.append(mensagem_usuario(entrada))
        r = self.api.messages.create(
            model=self.modelo, max_tokens=8000, system=self.sistema, tools=ferramentas_anthropic(),
            tool_choice={"type": "auto"}, output_config={"effort": self.effort},
            cache_control={"type": "ephemeral"}, messages=self.mensagens)
        self.uso.somar(r.usage)
        if r.stop_reason in ("refusal", "max_tokens"):
            raise Recusa(r.stop_reason)
        self.mensagens.append({"role": "assistant", "content": r.content})  # inteiro, com o raciocínio
        return {"texto": _texto(r),
                "chamadas": [{"id": b.id, "nome": b.name, "args": b.input} for b in r.content if b.type == "tool_use"]}


class ClienteSimulado:
    def __init__(self, api, c: Cenario, modelo: str = "claude-haiku-5-5"):
        self.api, self.modelo = api, modelo
        regra = "Insista em falar com uma pessoa da equipe até ser transferido." if c.tipo == "humano" else FRASE_HUMANO
        self.sistema = (PROMPTS / "cliente.md").read_text().format(
            EMPRESA=EMPRESA, nome=c.nome, objetivo=objetivo_cliente(c), fatos=fatos_cliente(c), estilo=c.estilo,
            regra_humano=regra)
        self.mensagens: list[dict] = []
        self.uso = Uso(modelo)

    def falar(self, texto_agente: str | None) -> str | None:
        if texto_agente is None:
            texto_agente = "(Comece a conversa.)"
        self.mensagens.append({"role": "user", "content": texto_agente.strip() or "(O atendente não escreveu nada.)"})
        r = self.api.messages.create(model=self.modelo, max_tokens=2000, system=self.sistema,
                                     output_config={"effort": "low"}, messages=self.mensagens)
        self.uso.somar(r.usage)
        if r.stop_reason in ("refusal", "max_tokens"):
            raise Recusa(f"cliente: {r.stop_reason}")
        self.mensagens.append({"role": "assistant", "content": r.content})
        texto = _texto(r).strip()
        return None if "[FIM]" in texto else texto
