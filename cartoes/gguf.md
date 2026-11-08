---
base_model: FMendonca/qwen3-1.7b-agente-suporte-ptbr
base_model_relation: quantized
license: apache-2.0
language: [pt]
pipeline_tag: text-generation
tags: [gguf, llama.cpp, agent, tool-calling, customer-support, portuguese]
---

# Qwen3-1.7B atendente de suporte, em GGUF para CPU

Esta é a versão em GGUF (Q8_0, 1,83 GB) do [Qwen3-1.7B com LoRA](https://huggingface.co/FMendonca/qwen3-1.7b-agente-suporte-ptbr) que atende o chat de suporte da Garfo Ligeiro, um app de delivery fictício. O LoRA foi fundido no modelo base e convertido com o llama.cpp, para rodar na CPU, sem GPU. A demo do repositório (`demo/app.py`) roda o adaptador em bf16, na GPU, ou este GGUF, na CPU, com `GGUF=arquivo python demo/app.py`.

O código, as medições e as limitações estão no [GitHub](https://github.com/fernandomcrsilva/agente-suporte-ptbr).

## Resultados nos 300 cenários de teste

Um caso conta como resolvido quando o estado final do sistema é igual ao que a política manda. Um erro grave é dar ao cliente algo a que ele não tinha direito.

| Versão | Resolvidos (IC 95%) | Erros graves | Tempo por fala (mediana) |
|---|---|---|---|
| Este GGUF (Q8_0), na CPU com 8 threads | 85,3% (81,3–89,3) | 15 | 3,2 s |
| O adaptador em bf16, na RX 7600 | 85,7% (81,7–89,3) | 19 | 2,5 s |

Nos 267 cenários em que o cliente simulado abriu a conversa do mesmo jeito nos dois testes, este GGUF e o adaptador em bf16 resolveram o mesmo número de casos: 226. A versão Q4_K_M, menor, rodou 79 cenários antes de ser descartada. Nos 72 em que a abertura foi igual, ela perdeu 12 casos que o bf16 resolvia e ganhou só 2, por isso não foi publicada.

## Formato da conversa

O modelo **não** foi treinado no template de chat nativo do Qwen3, que vem embutido neste arquivo. O formato está em [`src/formato_qwen.py`](https://github.com/fernandomcrsilva/agente-suporte-ptbr/blob/main/src/formato_qwen.py): toda fala do agente começa com um bloco `<think>` vazio, os resultados das ferramentas voltam numa fala `user` dentro de `<tool_response>` e a primeira fala do cliente vem depois de uma linha de contexto. Por isso, a forma certa de usar é montar os tokens com o tokenizer do Qwen3 e entregar ao llama.cpp, sem o `create_chat_completion`.

## Como usar

O exemplo usa o repositório clonado e precisa de `pip install llama-cpp-python==0.3.36 transformers==5.22.2 huggingface_hub`. O llama-cpp-python compila na instalação, o que leva alguns minutos. Não precisa de GPU nem de torch.

```python
# git clone https://github.com/fernandomcrsilva/agente-suporte-ptbr && cd agente-suporte-ptbr/src
from huggingface_hub import hf_hub_download

from aluno import SISTEMA_ALUNO, AgenteQwen, ModeloGGUF
from cenarios import gerar
from conversa import Sessao

caminho = hf_hub_download("FMendonca/qwen3-1.7b-agente-suporte-ptbr-gguf", "qwen3-1.7b-agente-suporte-ptbr-Q8_0.gguf")
modelo = ModeloGGUF(caminho, n_threads=4)
atendimento = Sessao(gerar(3_000_007, "atraso"), AgenteQwen(modelo, SISTEMA_ALUNO))
print(atendimento.responder("Meu pedido chegou mais de uma hora atrasado."))
print(atendimento.sistema.estado_final())
```

## Como foi feito

O [`src/gguf.py`](https://github.com/fernandomcrsilva/agente-suporte-ptbr/blob/main/src/gguf.py) funde o LoRA no Qwen3-1.7B em bf16, converte com o `convert_hf_to_gguf.py` e quantiza com o `llama-quantize`. Foi usado o llama.cpp no commit `0c1e570`, o mesmo do llama-cpp-python 0.3.36.

## Limitações

As mesmas do [adaptador](https://huggingface.co/FMendonca/qwen3-1.7b-agente-suporte-ptbr): cenários e cliente sintéticos, uma empresa fictícia e erros graves que exigem limites rígidos nas ferramentas.

## Licença

Apache 2.0, a mesma do Qwen3.
