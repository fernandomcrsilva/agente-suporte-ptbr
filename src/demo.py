"""Lógica da demo, sem Gradio: casos prontos, a conversa com uma pessoa, o painel do sistema e a conferência.

A tela fica em demo/app.py. Aqui o recrutador faz o papel do cliente e o aluno atende pelo mesmo loop do teste.
"""
import json
import time

from aluno import SISTEMA_ALUNO, AgenteQwen
from avaliar import avaliar
from cenarios import DEMO, fatos_cliente, gerar, objetivo_cliente
from conversa import Sessao
from modelos import Cenario, EstadoFinal, reais
from politica import esperado

CASOS = {
    "Pedido chegou atrasado": (DEMO + 7, "atraso"),  # a semente 7 atrasa 72 min e dá cupom; a 0 atrasava só 5 min
    "Item faltando ou errado": (DEMO + 1, "item"),
    "Reclamação depois do prazo de 48 horas": (DEMO + 2, "item_fora_prazo"),  # o ponto fraco medido do aluno
    "Diz que não chegou, mas o rastreio diz entregue": (DEMO + 3, "nao_chegou"),
    "Quer cancelar o pedido": (DEMO + 4, "cancelar"),
    "Tenta mudar as regras pelo chat": (DEMO + 5, "manipular"),
    "Pergunta pelo pedido de outra pessoa": (DEMO + 6, "pedido_de_outro"),
}
VAZIA = "(o atendente não escreveu nada)"
AVISOS = {
    "transferido": "O atendimento foi passado para uma pessoa da equipe e o agente saiu da conversa. "
                   "Para testar de novo, clique em Recomeçar ou escolha outro caso.",
    "limite_ferramentas": "O agente chamou ferramentas 6 vezes seguidas sem responder, e o sistema parou o "
                          "atendimento. Para testar de novo, clique em Recomeçar.",
    "contexto_cheio": "A conversa passou do contexto que o modelo consegue ler de uma vez (8.192 tokens). "
                      "Para testar de novo, clique em Recomeçar.",
}


def novo_atendimento(rotulo: str, modelo) -> Sessao:
    semente, tipo = CASOS[rotulo]
    return Sessao(gerar(semente, tipo), AgenteQwen(modelo, SISTEMA_ALUNO))


def papel(s: Sessao) -> str:
    return (f"**Seu papel:** {objetivo_cliente(s.c)}\n\n"
            f"**O que aconteceu de verdade (o agente não sabe):** {fatos_cliente(s.c)}")


def enviar(s: Sessao, texto: str) -> tuple[str, float]:
    """A fala do recrutador vai para o agente. Devolve a resposta e quantos segundos ela levou."""
    if not texto.strip():
        return "", 0.0
    inicio = time.perf_counter()
    try:
        resposta = s.responder(texto.strip())
    except ValueError:  # o ModeloGGUF recusa um prompt maior que o contexto
        s.motivo_fim, resposta = "contexto_cheio", ""
    return resposta.strip() or VAZIA, time.perf_counter() - inicio


def aviso_fim(motivo: str) -> str:
    return AVISOS[motivo]


def _estado(c: Cenario, e: EstadoFinal) -> list[str]:
    pedidos = {p.id: p for p in c.pedidos}
    linhas = []
    for pid, itens in sorted(e.reembolsos):
        p = pedidos[pid]
        if "todos" in itens:
            linhas.append(f"- Reembolso total do pedido {pid}: {reais(p.total)}")
        else:
            escolhidos = [i for i in p.itens if i.id in itens]
            linhas.append(f"- Reembolso no pedido {pid}: {', '.join(i.nome for i in escolhidos)} "
                          f"({reais(sum(i.preco for i in escolhidos))})")
    linhas += [f"- Cupom de {reais(v)} ligado ao pedido {pid}" for pid, v in sorted(e.cupons)]
    linhas += [f"- Pedido {pid} cancelado" for pid in sorted(e.cancelamentos)]
    if e.transferido:
        linhas.append("- Atendimento passado para uma pessoa da equipe")
    return linhas or ["- Nada mudou"]


def painel(s: Sessao) -> str:
    resultados = {e["id"]: e["resultado"] for e in s.eventos if e["papel"] == "ferramenta"}
    feitas = [ch for e in s.eventos if e["papel"] == "agente" for ch in e["chamadas"] if ch["id"] in resultados]
    linhas = ["### Ferramentas chamadas"]
    linhas += [f"{k}. `{ch['nome']}({json.dumps(ch['args'], ensure_ascii=False)})`  \n"
               f"→ `{json.dumps(resultados[ch['id']], ensure_ascii=False)[:300]}`" for k, ch in enumerate(feitas, 1)]
    if not feitas:
        linhas.append("Nenhuma ainda.")
    linhas += ["", "### O que mudou no sistema", *_estado(s.c, s.sistema.estado_final())]
    if s.sistema.bloqueios:
        linhas += ["", "**Tentativas que o sistema bloqueou:**",
                   *[f"- `{b['ferramenta']}`: {b['motivo']}" for b in s.sistema.bloqueios]]
    return "\n".join(linhas)


def conferencia(s: Sessao) -> str:
    r = avaliar(s.c, s.sistema.estado_final(), s.sistema.bloqueios)
    linhas = ["**O que a política manda neste caso:**", *_estado(s.c, esperado(s.c)), "",
              "Comparando com o estado do sistema agora:", f"**Resolvido certo: {'sim' if r.resolvido else 'não'}**"]
    if r.erros_graves:
        linhas += ["", "**Erros graves:**", *[f"- {g}" for g in r.erros_graves]]
    return "\n".join(linhas)
