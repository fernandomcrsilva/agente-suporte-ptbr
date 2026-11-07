"""Contagem de tokens e custo por modelo, para a Anthropic e o Workers AI."""
from dataclasses import dataclass

# US$ por milhão de tokens: entrada, saída, leitura de cache, escrita de cache
PRECOS = {
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50),
    "claude-haiku-5-5": (0.10, 0.50, 0.10, 0.125),  # ponytail: sem preço de cache do Haiku na tabela; usa o teto
    # Workers AI. A escrita de cache não é cobrada à parte; a leitura sai com desconto onde o modelo tem cache.
    "@cf/deepseek-ai/deepseek-v4.1-flash-1017": (0.30, 1.20, 0.006, 0.30),
    "@cf/zai-org/glm-4.7-flash": (0.06, 0.40, 0.06, 0.06),
    "@cf/openai/gpt-oss-120b": (0.35, 0.75, 0.35, 0.35),
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
            cache = (u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
            self.entrada += (u.get("prompt_tokens") or 0) - cache
            self.cache_leitura += cache
            self.saida += u.get("completion_tokens") or 0
            return
        self.entrada += u.input_tokens
        self.saida += u.output_tokens
        self.cache_leitura += u.cache_read_input_tokens or 0
        self.cache_escrita += u.cache_creation_input_tokens or 0

    def custo(self) -> float:
        e, s, cl, ce = PRECOS[self.modelo]
        return (self.entrada * e + self.saida * s + self.cache_leitura * cl + self.cache_escrita * ce) / 1e6
