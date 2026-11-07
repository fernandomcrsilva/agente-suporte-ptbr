"""Professor e cliente simulado abertos, no Workers AI da Cloudflare, no formato de chat da OpenAI.

As conversas de treino saem daqui: a Política de Uso da Anthropic proíbe treinar modelos com saídas do Claude.
O modelo, nos dois papéis, é o DeepSeek V4.1 Flash, de licença MIT. O gpt-oss-120b foi descartado: no Workers AI, as chamadas de ferramenta dele
voltavam como marcadores internos (`<|channel|>commentary to=functions...`) no meio do texto, e o GLM-4.7 Flash,
como cliente, saía vazio ou num português estranho (testes de 07/11/2026).
"""
import json
import time

import requests

from conversa import Recusa
from custo import Uso
from modelos import Cenario
from prompts import cliente as prompt_cliente
from prompts import fala_do_agente, professor
from sistema import ferramentas_openai

PROFESSOR = "@cf/deepseek-ai/deepseek-v4.1-flash-1017"
CLIENTE = PROFESSOR  # sem raciocínio: o cliente só fala
URL = "https://api.cloudflare.com/client/v4/accounts/{conta}/ai/v1/chat/completions"


class WorkersAI:
    def __init__(self, conta: str, token: str, sessao=None, tentativas: int = 5, espera: float = 2.0):
        self.url = URL.format(conta=conta)
        self.sessao = sessao or requests.Session()
        self.sessao.headers["Authorization"] = f"Bearer {token}"
        self.tentativas, self.espera = tentativas, espera

    def completar(self, **corpo) -> dict:
        erro = ""
        for k in range(self.tentativas):
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
            time.sleep(self.espera * 2 ** k)
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
    def __init__(self, api, c: Cenario, modelo: str = CLIENTE, esforco: str = "none"):
        self.api, self.modelo, self.esforco = api, modelo, esforco
        self.sistema = prompt_cliente(c)
        self.mensagens: list[dict] = [{"role": "system", "content": self.sistema}]
        self.uso = Uso(modelo)

    def falar(self, texto_agente: str | None) -> str | None:
        self.mensagens.append({"role": "user", "content": fala_do_agente(texto_agente)})
        msg = _resposta(self.api.completar(model=self.modelo, messages=self.mensagens, reasoning_effort=self.esforco,
                                           max_tokens=2000), self.uso)
        texto = (msg.get("content") or "").strip()
        self.mensagens.append({"role": "assistant", "content": texto})
        return None if "[FIM]" in texto else texto
