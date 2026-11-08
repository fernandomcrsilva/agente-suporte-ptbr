"""Professor e cliente simulado abertos, no Workers AI da Cloudflare, no formato de chat da OpenAI.

As conversas de treino saem daqui: a Política de Uso da Anthropic proíbe treinar modelos com saídas do Claude.
Professor: DeepSeek V4.1 Flash (MIT). Cliente: Mistral Small 3.1 (Apache 2.0). Testes de 07/11/2026:
- o gpt-oss-120b foi descartado: no Workers AI, as chamadas de ferramenta dele voltavam como marcadores internos
  (`<|channel|>commentary to=functions...`) no meio do texto;
- como cliente, o GLM-4.7 Flash saía vazio ou num português estranho, e o gpt-oss-20b encerrava na primeira fala;
- o DeepSeek é modelo do plano pago, limitado a 20 requisições por minuto, por isso o cliente fica num modelo do
  limite padrão (300 por minuto) e as chamadas do professor são espaçadas.
"""
import json
import threading
import time

import requests

from conversa import Recusa
from custo import Uso
from modelos import Cenario
from prompts import cliente as prompt_cliente
from prompts import fala_do_agente, professor
from sistema import ferramentas_openai

PROFESSOR = "@cf/deepseek-ai/deepseek-v4.1-flash-1017"
CLIENTE = "@cf/mistralai/mistral-small-3.1-24b-instruct"
LIMITES = {PROFESSOR: 18}  # requisições por minuto; o limite da Cloudflare é 20, com folga para não bater nele
URL = "https://api.cloudflare.com/client/v4/accounts/{conta}/ai/v1/chat/completions"


class WorkersAI:
    def __init__(self, conta: str, token: str, sessao=None, tentativas: int = 8, espera: float = 5.0,
                 limites: dict[str, int] | None = None, dormir=time.sleep, relogio=time.monotonic):
        self.url = URL.format(conta=conta)
        self.sessao = sessao or requests.Session()
        self.sessao.headers["Authorization"] = f"Bearer {token}"
        self.tentativas, self.espera = tentativas, espera
        self.intervalo = {m: 60 / n for m, n in (limites or {}).items()}
        self.dormir, self.relogio = dormir, relogio
        self._trava, self._proxima = threading.Lock(), {}

    def _aguardar_vez(self, modelo: str) -> None:
        """Espaça as chamadas de um modelo com limite por minuto, somando todas as threads."""
        intervalo = self.intervalo.get(modelo)
        if not intervalo:
            return
        with self._trava:
            agora = self.relogio()
            vez = max(agora, self._proxima.get(modelo, 0.0))
            self._proxima[modelo] = vez + intervalo
        if vez > agora:
            self.dormir(vez - agora)

    def completar(self, **corpo) -> dict:
        erro = ""
        for k in range(self.tentativas):
            self._aguardar_vez(corpo.get("model", ""))
            espera = self.espera * 2 ** k
            try:
                r = self.sessao.post(self.url, json=corpo, timeout=180)
            except requests.RequestException as e:
                erro = f"{type(e).__name__}"
            else:
                if r.status_code == 200:
                    return r.json()
                erro = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code not in (408, 429) and r.status_code < 500:
                    break  # erro do pedido: tentar de novo não resolve
                pedido = r.headers.get("retry-after")
                if pedido and pedido.replace(".", "", 1).isdigit():
                    espera = float(pedido)
            if k < self.tentativas - 1:
                self.dormir(min(espera, 120))
        raise RuntimeError(f"Workers AI falhou: {erro}")


def _resposta(r: dict, uso: Uso) -> dict:
    uso.somar(r.get("usage") or {})
    escolha = r["choices"][0]
    if escolha.get("finish_reason") == "length":
        raise Recusa("length")  # o raciocínio pode comer o max_tokens inteiro
    return escolha["message"]


class ProfessorAberto:
    def __init__(self, api, modelo: str = PROFESSOR, esforco: str = "low"):
        self.api, self.modelo, self.esforco = api, modelo, esforco
        self.mensagens: list[dict] = [{"role": "system", "content": professor()}]
        self.uso = Uso(modelo)

    def passo(self, entrada: list[dict]) -> dict:
        textos = [e["texto"] for e in entrada if e["papel"] != "ferramenta"]
        if textos:
            self.mensagens.append({"role": "user", "content": "\n\n".join(textos)})
        self.mensagens += [{"role": "tool", "tool_call_id": e["id"],
                            "content": json.dumps(e["resultado"], ensure_ascii=False)}
                           for e in entrada if e["papel"] == "ferramenta"]
        msg = _resposta(self.api.completar(
            model=self.modelo, messages=self.mensagens, tools=ferramentas_openai(), tool_choice="auto",
            reasoning_effort=self.esforco, max_tokens=8000), self.uso)
        chamadas = []
        for tc in msg.get("tool_calls") or []:
            bruto = tc["function"].get("arguments") or "{}"
            try:
                args = json.loads(bruto) if isinstance(bruto, str) else bruto
            except json.JSONDecodeError:
                args = {"_argumentos_invalidos": bruto}  # o sistema devolve erro, e o professor vê o erro
            chamadas.append({"id": tc["id"], "nome": tc["function"]["name"], "args": args})
        guardada = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            guardada["tool_calls"] = msg["tool_calls"]
        self.mensagens.append(guardada)
        return {"texto": msg.get("content") or "", "chamadas": chamadas}


class ClienteAberto:
    def __init__(self, api, c: Cenario, modelo: str = CLIENTE, temperatura: float | None = None):
        self.api, self.modelo = api, modelo
        self.extra = {} if temperatura is None else {"temperature": temperatura}
        self.sistema = prompt_cliente(c)
        self.mensagens: list[dict] = [{"role": "system", "content": self.sistema}]
        self.uso = Uso(modelo)

    def falar(self, texto_agente: str | None) -> str | None:
        self.mensagens.append({"role": "user", "content": fala_do_agente(texto_agente)})
        msg = _resposta(self.api.completar(model=self.modelo, messages=self.mensagens, max_tokens=1000,
                                           **self.extra), self.uso)
        texto = (msg.get("content") or "").strip()
        self.mensagens.append({"role": "assistant", "content": texto})
        return None if "[FIM]" in texto else texto
