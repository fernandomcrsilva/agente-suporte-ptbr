"""Contagem de tokens e custo por modelo, para a Anthropic e o Workers AI."""
from dataclasses import dataclass

# US$ por milhão de tokens: entrada, saída, leitura de cache, escrita de cache
PRECOS = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.10, 0.125),  # ponytail: sem preço de cache do Haiku na tabela; usa o teto
    "@cf/openai/gpt-oss-120b": (0.35, 0.75, 0.35, 0.35),  # Workers AI, sem desconto de cache
    "@cf/openai/gpt-oss-20b": (0.20, 0.30, 0.20, 0.20),
}


@dataclass
class Uso:
    modelo: str
    entrada: int = 0
    saida: int = 0
    cache_leitura: int = 0
    cache_escrita: int = 0

    def somar(self, u) -> None:
        """Aceita o `usage` da Anthropic (objeto) ou o do formato OpenAI (dict)."""
        if isinstance(u, dict):
            self.entrada += u.get("prompt_tokens") or 0
            self.saida += u.get("completion_tokens") or 0
            return
        self.entrada += u.input_tokens
        self.saida += u.output_tokens
        self.cache_leitura += u.cache_read_input_tokens or 0
        self.cache_escrita += u.cache_creation_input_tokens or 0

    def custo(self) -> float:
        e, s, cl, ce = PRECOS[self.modelo]
        return (self.entrada * e + self.saida * s + self.cache_leitura * cl + self.cache_escrita * ce) / 1e6
