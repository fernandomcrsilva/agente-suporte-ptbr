---
base_model: Qwen/Qwen3-1.7B
library_name: peft
license: apache-2.0
language: [pt]
pipeline_tag: text-generation
datasets: [FMendonca/conversas-suporte-delivery-ptbr]
tags: [lora, agent, tool-calling, customer-support, portuguese, distillation, rocm]
---

# Qwen3-1.7B com LoRA para atender clientes de um delivery fictício

Este adaptador LoRA faz o [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) atender o chat de suporte da Garfo Ligeiro, um app de delivery fictício. O modelo conversa com o cliente e chama as ferramentas de um sistema de pedidos simulado: ele lista e detalha pedidos, rastreia entregas, reembolsa itens, emite cupons, cancela pedidos e transfere o caso para uma pessoa. A política da empresa não vai no prompt. Ele aprendeu as regras pelos exemplos.

O treino rodou numa Radeon RX 7600 de 8 GB, com ROCm, sobre 1.874 conversas escritas por um professor aberto, o DeepSeek V4.1 Flash. O [código, as medições e as limitações](https://github.com/fernandomcrsilva/agente-suporte-ptbr) estão no GitHub. Também há uma [versão em GGUF para CPU](https://huggingface.co/FMendonca/qwen3-1.7b-agente-suporte-ptbr-gguf) e uma demo para conversar com ele, que roda este adaptador em casa (`demo/app.py` no repositório). A versão pública da demo, no Hugging Face, entra no ar em dezembro de 2026.

## Resultados nos 300 cenários de teste

Um caso conta como resolvido quando o estado final do sistema (reembolsos, cupons, cancelamentos e transferência) é igual ao que a política manda. Um erro grave é dar ao cliente algo a que ele não tinha direito. Os 300 cenários nunca entraram no treino, e todos os sistemas conversaram com o mesmo cliente simulado.

| Sistema | Resolvidos (IC 95%) | Erros graves | Clareza (juiz, 1 a 5) |
|---|---|---|---|
| Este adaptador, em bf16 na RX 7600 | 85,7% (81,7–89,3) | 19 | 4,4 |
| O mesmo Qwen3-1.7B sem treino, com a política inteira no prompt | 53,3% (47,7–59,0) | 0 | 1,8 |
| O professor, DeepSeek V4.1 Flash | 98,0% (96,0–99,3) | 0 | 4,7 |

O ponto fraco está nas reclamações de item feitas depois do prazo de 48 horas. Nesse tipo, ele resolveu só 10 de 22 casos, e 9 dos 19 erros graves vêm daí: ele lê a data, sabe a regra e reembolsa assim mesmo.

## Formato da conversa

O adaptador **não** foi treinado no template de chat nativo do Qwen3. O formato está em [`src/formato_qwen.py`](https://github.com/fernandomcrsilva/agente-suporte-ptbr/blob/main/src/formato_qwen.py):

- o prompt de sistema tem duas frases de papel e as definições curtas das ferramentas, no bloco `<tools>` do Qwen3;
- toda fala do agente começa com um bloco `<think>` vazio, mantido também nas falas antigas da conversa;
- os resultados das ferramentas voltam numa fala `user`, cada um dentro de `<tool_response>`;
- a primeira fala do cliente vem depois de uma linha de contexto, como `Cliente logado: Ana (C1). Agora: 07/11 20:30.`.

O modelo nunca viu o formato do `apply_chat_template` do Qwen3, e o resultado com ele não foi medido. O caminho mais curto é usar o código do repositório.

## Como usar

O exemplo precisa de uma GPU (CUDA ou ROCm) e do repositório clonado.

```python
# git clone https://github.com/fernandomcrsilva/agente-suporte-ptbr && cd agente-suporte-ptbr/src
from aluno import SISTEMA_ALUNO, AgenteQwen, ModeloQwen
from cenarios import gerar
from conversa import Sessao

modelo = ModeloQwen(adaptador="FMendonca/qwen3-1.7b-agente-suporte-ptbr")
atendimento = Sessao(gerar(3_000_007, "atraso"), AgenteQwen(modelo, SISTEMA_ALUNO))
print(atendimento.responder("Meu pedido chegou mais de uma hora atrasado."))
print(atendimento.sistema.estado_final())
```

## Treino

| Medida | Valor |
|---|---|
| Conversas | 1.874 de treino e 99 de validação |
| LoRA | posto 16, alfa 32, nas sete projeções |
| Passos | 235 (2 épocas, batch 2 com acumulação de 8, taxa 2e-4) |
| Perda de validação | 2,066 antes de treinar e 0,367 no fim |
| Tempo e memória | 1 h 59 min, com pico de 5,55 GB de VRAM |

A perda conta só nas falas do agente.

## Limitações

- Os cenários e o cliente são sintéticos. Um cliente simulado escreve de forma mais limpa e previsível que um cliente de verdade.
- A política é de uma empresa fictícia. O modelo não serve para atendimento real sem outro treino.
- Ele comete erros graves: 19 em 300 conversas. Num sistema de verdade, os limites rígidos precisam ficar nas ferramentas, como no sistema simulado do projeto, que barra reembolsos acima do teto e cupons fora da política.
- O aluno foi treinado uma vez só, com uma semente.

## Licença

Apache 2.0, a mesma do Qwen3. As conversas de treino estão no dataset [conversas-suporte-delivery-ptbr](https://huggingface.co/datasets/FMendonca/conversas-suporte-delivery-ptbr), em CC BY 4.0.
