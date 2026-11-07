"""Professor e cliente simulado no Claude, com a contagem de custo de cada um.

Pela Política de Uso da Anthropic, as saídas do Claude não podem treinar modelos sem autorização. Aqui o Claude
serve só para medir: é a linha de referência no teste. As conversas de treino saem de `aberto.py`.
"""
import json

from conversa import Recusa
from custo import PRECOS, Uso  # noqa: F401  (PRECOS reexportado para quem já importava daqui)
from modelos import Cenario
from prompts import FRASE_HUMANO, PROMPTS, fala_do_agente, professor  # noqa: F401
from prompts import cliente as prompt_cliente
from sistema import ferramentas_anthropic


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
        self.sistema = professor()
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
        self.sistema = prompt_cliente(c)
        self.mensagens: list[dict] = []
        self.uso = Uso(modelo)

    def falar(self, texto_agente: str | None) -> str | None:
        self.mensagens.append({"role": "user", "content": fala_do_agente(texto_agente)})
        r = self.api.messages.create(model=self.modelo, max_tokens=2000, system=self.sistema,
                                     output_config={"effort": "low"}, messages=self.mensagens)
        self.uso.somar(r.usage)
        if r.stop_reason in ("refusal", "max_tokens"):
            raise Recusa(f"cliente: {r.stop_reason}")
        self.mensagens.append({"role": "assistant", "content": r.content})
        texto = _texto(r).strip()
        return None if "[FIM]" in texto else texto
