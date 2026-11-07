"""Conversas no formato de ferramentas do Qwen3, com a perda só nas falas do agente.

O raciocínio vazio fica em todas as falas do agente, inclusive nas antigas. O template nativo do Qwen3 tira esse
bloco da história, mas aqui treino e inferência montam o prompt do mesmo jeito, então ele fica.
"""
import json

from cenarios import EMPRESA
from sistema import ferramentas_qwen

PROMPT_ALUNO = (f"Você é o atendente de suporte da {EMPRESA}, um app de delivery de comida. "
                "Resolva o problema do cliente seguindo a política da empresa e usando as ferramentas.")
INICIO_AGENTE = "<|im_start|>assistant\n<think>\n\n</think>\n\n"


def prompt_sistema(tok) -> str:
    return tok.apply_chat_template([{"role": "system", "content": PROMPT_ALUNO}], tools=ferramentas_qwen(),
                                   tokenize=False)


def corpo(evento: dict) -> str:
    partes = [evento["texto"].strip()] if evento["texto"].strip() else []
    partes += ["<tool_call>\n" + json.dumps({"name": ch["nome"], "arguments": ch["args"]}, ensure_ascii=False)
               + "\n</tool_call>" for ch in evento["chamadas"]]
    return "\n".join(partes)


def _pedacos(eventos: list[dict], tok) -> list[tuple[str, bool]]:
    """(texto, entra na perda?) na ordem do prompt."""
    out, contexto, respostas = [(prompt_sistema(tok), False)], None, []

    def fechar_respostas():
        if respostas:
            out.append(("<|im_start|>user\n" + "\n".join(
                "<tool_response>\n" + json.dumps(r, ensure_ascii=False) + "\n</tool_response>" for r in respostas)
                + "<|im_end|>\n", False))
            respostas.clear()

    for e in eventos:
        if e["papel"] != "ferramenta":
            fechar_respostas()
        if e["papel"] == "contexto":
            contexto = e["texto"]
        elif e["papel"] == "cliente":
            texto = f"{contexto}\n\n{e['texto']}" if contexto else e["texto"]
            contexto = None
            out.append((f"<|im_start|>user\n{texto}<|im_end|>\n", False))
        elif e["papel"] == "agente":
            out += [(INICIO_AGENTE, False), (corpo(e) + "<|im_end|>", True), ("\n", False)]
        elif e["papel"] == "ferramenta":
            respostas.append(e["resultado"])
    fechar_respostas()
    return out


def renderizar(eventos: list[dict], tok) -> tuple[list[int], list[int]]:
    ids, rotulos = [], []
    for texto, perda in _pedacos(eventos, tok):
        x = tok(texto, add_special_tokens=False)["input_ids"]
        ids += x
        rotulos += x if perda else [-100] * len(x)
    return ids, rotulos


def prompt_geracao(eventos: list[dict], tok) -> list[int]:
    return renderizar(eventos, tok)[0] + tok(INICIO_AGENTE, add_special_tokens=False)["input_ids"]
