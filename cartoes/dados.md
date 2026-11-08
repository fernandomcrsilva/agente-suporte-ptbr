---
license: cc-by-4.0
language: [pt]
task_categories: [text-generation]
tags: [synthetic, customer-support, tool-calling, agent, portuguese]
size_categories: [1K<n<10K]
pretty_name: Conversas de suporte de delivery em português
configs:
  - config_name: default
    data_files:
      - split: train
        path: treino.jsonl
      - split: validation
        path: validacao.jsonl
---

# Conversas de suporte de um delivery fictício, com chamadas de ferramenta

São 1.973 conversas sintéticas em português do Brasil entre um cliente e o atendente de suporte da Garfo Ligeiro, um app de delivery fictício. O atendente consulta um sistema de pedidos simulado por ferramentas e resolve o caso pela política da empresa. Foram essas as conversas que treinaram o [Qwen3-1.7B com LoRA](https://huggingface.co/FMendonca/qwen3-1.7b-agente-suporte-ptbr) do projeto [agente-suporte-ptbr](https://github.com/fernandomcrsilva/agente-suporte-ptbr).

## Como foram feitas

- **Cenários:** um gerador com semente fixa cria o cliente, os pedidos e o que aconteceu de verdade com eles. Os cenários de treino usam as sementes de 0 a 1.999 e cobrem 14 tipos de caso, de atraso e item faltando a tentativa de mudar as regras pelo chat.
- **Atendente:** o DeepSeek V4.1 Flash (licença MIT), no Workers AI da Cloudflare, atendeu num loop real com as ferramentas. Os resultados das ferramentas vêm sempre do código do sistema simulado, nunca do modelo.
- **Cliente:** o Mistral Small 3.1 (Apache 2.0), também no Workers AI, fez o papel do cliente. Ele só sabia os fatos do cenário.
- **Filtro:** de 2.000 conversas, ficaram as 1.973 em que o estado final do sistema saiu igual ao que a política manda e que terminaram de verdade, pelo cliente ou por transferência.
- **Limpeza:** quando o atendente chama uma ferramenta, o texto dessa fala sai, porque o cliente não o vê. Chamadas que nunca rodaram também saem.

Nenhuma conversa foi escrita pelo Claude, que no projeto só serve de referência e de juiz na avaliação.

## Arquivos

| Arquivo | Split | Conversas |
|---|---|---|
| `treino.jsonl` | `train` | 1.874 |
| `validacao.jsonl` | `validation` | 99 |

```python
from datasets import load_dataset

conversas = load_dataset("FMendonca/conversas-suporte-delivery-ptbr")
print(conversas["train"][0]["eventos"][1])  # a primeira fala do cliente
```

As conversas têm 1.412 tokens em média no formato de treino do Qwen3, e a maior tem 2.945.

## Formato

Cada linha é um objeto JSON com um campo, `eventos`: a lista de eventos da conversa, em ordem.

| `papel` | Campos |
|---|---|
| `contexto` | `texto`: quem está logado e a hora, como `Cliente logado: Diego (C1). Agora: 02/11 17:24.` |
| `cliente` | `texto` |
| `agente` | `texto` e `chamadas`, uma lista de `{"id", "nome", "args"}` |
| `ferramenta` | `id`, `nome` e `resultado`, o JSON que o sistema devolveu |

As linhas não trazem o cenário, a semente nem o estado esperado. Para isso, use o gerador do repositório (`src/cenarios.py`). Os valores em dinheiro aparecem como texto, no formato `R$ 87,00`.

## Limitações

- Tudo é sintético. Clientes reais escrevem de formas que o gerador e o cliente simulado não preveem.
- O filtro guarda só as conversas em que o atendente acertou o estado final. Por isso, quase não há exemplos de erro e correção.
- A empresa, os clientes, os restaurantes e os pedidos são inventados.

## Licença

CC BY 4.0.
