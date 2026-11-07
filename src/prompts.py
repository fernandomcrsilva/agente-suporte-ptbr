"""Prompts do professor e do cliente simulado, iguais para qualquer provedor."""
from pathlib import Path

from cenarios import EMPRESA, fatos_cliente, objetivo_cliente
from modelos import Cenario

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
FRASE_HUMANO = "Nunca peça para falar com um humano."
ABERTURA = "(Comece a conversa.)"


def professor() -> str:
    return (PROMPTS / "professor.md").read_text().replace("{EMPRESA}", EMPRESA)


def cliente(c: Cenario) -> str:
    regra = "Insista em falar com uma pessoa da equipe até ser transferido." if c.tipo == "humano" else FRASE_HUMANO
    return (PROMPTS / "cliente.md").read_text().format(
        EMPRESA=EMPRESA, nome=c.nome, objetivo=objetivo_cliente(c), fatos=fatos_cliente(c), estilo=c.estilo,
        regra_humano=regra)


def fala_do_agente(texto: str | None) -> str:
    """O que o cliente simulado recebe: a abertura, ou a fala do agente (a API não aceita mensagem vazia)."""
    if texto is None:
        return ABERTURA
    return texto.strip() or "(O atendente não escreveu nada.)"
