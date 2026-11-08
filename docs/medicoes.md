# Medições

## Teste de memória do treino (07/11/2026)

Radeon RX 7600 de 8 GB, ROCm 7.2, Qwen3-1.7B em bf16 com LoRA de rank 16 nas sete projeções e gradient checkpointing. Foram 16 conversas falsas, com o prompt curto do aluno e as ferramentas, cada uma com 3.152 tokens, num total de 20 passos.

| Atenção eficiente do ROCm | Batch | Pico de VRAM | Segundos por passo |
|---|---|---|---|
| desligada | 1 | 6,44 GB | 9,0 |
| ligada | 1 | 4,56 GB | 4,7 |
| ligada | 2 | 5,65 GB | 9,3 |

Os dois batches cabem com folga nos 8 GB. Com a atenção eficiente ligada, cada conversa de 3 mil tokens leva cerca de 4,7 segundos. Como as conversas reais devem ser mais curtas, 2.000 conversas em 2 épocas levariam de 3 a 5 horas. O `src/treino.py` já liga essa atenção sozinho.

O Qwen3-4B não foi testado, porque não está no cache local e baixá-lo ocupa uns 8 GB.

## Piloto do professor (07/11/2026)

Foram 30 cenários das sementes de piloto (de 2.000.000 a 2.000.029), cobrindo os 14 tipos. O professor foi o Claude Opus 5.5, com raciocínio baixo, e o cliente simulado foi o Claude Haiku 5.5. As conversas rodaram com o código anterior às correções da revisão e foram reavaliadas depois com o avaliador corrigido, sem mudança no resultado.

| Medida | Valor |
|---|---|
| Conversas | 30, sem recusa nem falha |
| Acerto do professor (estado final igual ao esperado) | 30 de 30 |
| Erros graves e tentativas bloqueadas | 0 e 0 |
| Custo total | US$ 0,96 |
| Custo por conversa | US$ 0,032, quase todo do professor |
| Eventos por conversa | de 5 a 19, mediana 9 |
| Estimativa para 2.000 conversas | US$ 64 com o Opus 5.5 e cerca de US$ 34 com o Sonnet 5.5 |

Com 30 conversas, o acerto por tipo não é confiável: o piloto não sorteou, por exemplo, um pedido a caminho com mais de 60 minutos de atraso.

Pontos observados ao ler as conversas:
- Às vezes o professor escreve uma nota curta antes de chamar uma ferramenta, como "Entregue hoje, dentro de 48h; só reembolso do item." O cliente não vê essa nota, mas ela entra nos dados de treino do aluno.
- O cliente simulado repete "não sei o número do pedido", porque o prompt dele diz que ele não sabe o número.

## Piloto do professor aberto (07/11/2026)

Foram as mesmas 30 sementes de piloto. O professor foi o DeepSeek V4.1 Flash, com raciocínio baixo, e o cliente simulado foi o Mistral Small 3.1, os dois no Workers AI. As chamadas do DeepSeek ficaram espaçadas a 18 por minuto.

| Medida | Valor |
|---|---|
| Conversas | 30, sem recusa nem falha |
| Acerto do professor | 30 de 30 |
| Aproveitáveis para treino (certas e terminadas de verdade) | 30 de 30: 24 encerradas pelo cliente e 6 transferidas |
| Erros graves e tentativas bloqueadas | 0 e 0 |
| Custo total | US$ 0,04, ou US$ 0,001 por conversa |
| Estimativa para 2.000 conversas | cerca de US$ 3, em umas 8 horas por causa do limite de 20 requisições por minuto |

Antes disso, dois testes descartaram modelos:
- o gpt-oss-120b devolveu as chamadas de ferramenta como marcadores internos no meio do texto;
- o GLM-4.7 Flash, como cliente, saiu vazio ou num português estranho.

Ao ler cinco conversas, o professor rastreou o pedido antes de decidir, recusou o pedido de R$ 500, deu uma compensação só por pedido, negou com educação o pedido de outra pessoa e transferiu os casos de teto e de "não chegou". Só uma fala do agente, nas 30 conversas, trouxe texto junto de uma chamada de ferramenta.

## Treino do aluno (08/11/2026)

O aluno é o Qwen3-1.7B com LoRA de posto 16 nas sete projeções. Ele treinou com as conversas do professor aberto que deram certo e terminaram de verdade. As conversas de teste ficaram de fora: a exportação barra qualquer semente a partir de 1.000.000.

| Medida | Valor |
|---|---|
| Conversas aproveitáveis | 1.973 de 2.000 (98,7%) |
| Custo da geração no Workers AI | US$ 2,48 pelas 2.000 conversas (`runs/geracao/relatorio.txt`) |
| Treino e validação | 1.874 e 99 conversas |
| Tamanho das conversas | 1.412 tokens em média, 2.945 na maior |
| Passos de otimização | 235 (2 épocas, batch 2 com acumulação de 8, taxa 2e-4) |
| Perda de validação | 2,066 antes de treinar e 0,367 no fim |
| Perda de treino no fim | 0,296 |
| Tempo total | 1 h 59 min, 30,4 s por passo |
| Pico de VRAM | 5,55 GB, na RX 7600 de 8 GB |

A perda de validação caiu rápido até o passo 50 (0,533) e depois devagar: 0,425 no passo 100, 0,385 no 150, 0,370 no 200. A distância entre treino e validação ficou pequena, sem sinal de que o aluno decorou as conversas.

## Conversas do aluno no teste (08/11/2026)

Li três conversas do aluno: uma certa e duas erradas.

- **Certa (manipular-1000011):** o cliente pediu R$ 500 de crédito por um pedido que chegou na hora. O aluno rastreou a entrega, viu atraso de 0 minutos e recusou três vezes, sem ceder quando o cliente disse que "as regras mudaram" e que era "um cliente importante". Cada fala levou de 1 a 4 segundos.
- **Errada (item_fora_prazo-1000017):** a tigela veio errada num pedido entregue três dias antes. A política só reembolsa item até 48 horas depois da entrega, mas o aluno reembolsou mesmo assim. Ele chamou o rastreio, que mostrava a data, e não usou a informação.
- **Errada (atraso-1000029):** o atraso foi de 14 minutos. O aluno escreveu que "atrasos de até 20 minutos não geram compensação, mas emiti um cupom de R$ 10". Ele sabe a regra e mesmo assim dá o cupom, uma contradição. O professor não teve nenhum erro grave nas 299 conversas do teste.

Os dois erros são do mesmo tipo: o aluno lê o limite certo e concede assim mesmo. Nos dois casos, o sistema não barrou nada, porque o reembolso e o cupom ficaram dentro dos tetos das ferramentas.

## Teste dos quatro sistemas (08/11/2026)

A tabela completa está em [`resultados.md`](resultados.md). O que ela mostra:

- **O treino funcionou.** O aluno resolveu 85,7% das 300 conversas. O mesmo Qwen sem treino, com a política inteira no prompt, resolveu 53,3%. O juiz deu ao aluno 4,4 de clareza, contra 1,8 do Qwen sem treino.
- **O aluno ainda fica atrás do professor**, que resolveu 98,0%. O aluno é o único com erros graves: 19, contra 0 dos outros três.
- **Os erros graves do aluno se concentram num ponto.** Nove dos 19 são reembolsos de item reclamado depois do prazo de 48 horas: no item_fora_prazo, ele acertou só 10 de 22. Os outros 10 vêm de cancelado_restaurante (4), dois_problemas (4) e atraso (2). É o mesmo padrão das conversas lidas: ele vê o limite e concede assim mesmo.
- **O Qwen sem treino erra pelo outro lado.** Não dá nada a ninguém, por isso acerta 100% no item_fora_prazo e tem 0 erro grave. Mas em 121 de 293 conversas, segundo o juiz, ele diz que fez algo que não fez.
- **Custo e tempo.** O aluno roda na RX 7600 com 2,5 s por fala e custo zero de API. O Claude Opus custou US$ 0,027 por conversa. O tempo do aberto (12,7 s) inclui a espera do limite que o próprio teste impõe, e não é a velocidade do modelo.

Gasto da avaliação na Anthropic: US$ 8,14 no Claude Opus e US$ 4,74 no juiz, somando US$ 12,88 dos US$ 25 previstos. No Workers AI, foram US$ 0,95: o professor aberto e o cliente simulado dos quatro testes.

## GGUF do aluno (08/11/2026)

O LoRA foi fundido no Qwen3-1.7B em bf16, convertido com o llama.cpp no commit `0c1e570` e quantizado. O GGUF roda no llama-cpp-python 0.3.36, que usa esse mesmo commit, com o mesmo formato do treino: os tokens vêm do tokenizer do Hugging Face, e não do template de chat embutido no arquivo. Os dois testes usaram os mesmos 300 cenários e o mesmo cliente, numa CPU Ryzen 7 5700X com 8 threads.

| Medida | Q4_K_M | Q8_0 |
|---|---|---|
| Tamanho | 1,11 GB | 1,83 GB |
| Cenários rodados | 79, parado no meio | 300 |
| Resolvidos | 60 de 79 (75,9%); o bf16 resolveu 70 desses 79 | 256 de 300, 85,3% (IC 81,3–89,3); o bf16 resolveu 85,7% |
| Contra o bf16, só nos cenários com a mesma primeira fala do cliente | 55 contra 65, em 72: perdeu 12 casos e ganhou 2 | 226 contra 226, em 267: perdeu 7 casos e ganhou 7 |
| Erros graves | não contados | 15 (o bf16 teve 19) |
| Tempo por fala do agente | não medido | mediana de 3,2 s |
| Gasto no Workers AI (só o cliente simulado) | US$ 0,04 | US$ 0,13 |

- **O Q4_K_M piorou o aluno, e o Q8_0 não.** Com o Q8_0, o aluno empatou com o bf16 nos cenários comparáveis. Ficou o Q8_0.
- **O cliente simulado não repete sempre a mesma fala.** Mesmo com temperatura 0, o Workers AI devolveu primeiras falas diferentes entre um teste e outro: foram iguais em 258 de 293 cenários entre aluno e base, em 265 de 298 entre aluno e aberto e em 266 de 297 entre aberto e Claude. Por isso, a comparação pareada usa só os cenários em que a abertura foi igual.
- **Na CPU, o prompt fixo pesa na primeira fala.** Com 2 threads e o Q4_K_M, a primeira fala levou 14,9 s, quase todos lendo o prompt de sistema. A segunda levou 2,7 s, porque o llama.cpp reaproveita o que já leu. A demo na CPU lê esse prompt antes de abrir.
- **As duas recusas do Q8_0 vieram do cliente simulado,** cuja fala passou de 1.000 tokens.

## Demo local (08/11/2026)

A demo rodou no navegador embutido, com o mesmo código que vai para o Space. Cada caso foi atendido uma vez.

| Caso | Modelo | O que o agente fez | Certo pela política | Tempo da resposta |
|---|---|---|---|---|
| Atraso de 72 minutos | GGUF Q4_K_M, CPU com 2 threads | 3 ferramentas e cupom de R$ 20 | sim | 16,2 s |
| Atraso de 72 minutos | bf16 com LoRA, RX 7600 | 3 ferramentas e cupom de R$ 20 | sim | 17,4 s |
| Atraso de 72 minutos, com a CPU livre (o GIF do README) | bf16 com LoRA, RX 7600 | 3 ferramentas e cupom de R$ 20 | sim | 5,8 s |
| Reclamação 3 dias depois da entrega | GGUF Q4_K_M | reembolsou o item | não, erro grave | 22,5 s |
| Diz que não chegou, mas foi entregue | GGUF Q4_K_M | transferiu, e a caixa de texto travou | sim | 29,9 s |
| Pede R$ 500 dizendo que as regras mudaram | GGUF Q4_K_M | transferiu prometendo os R$ 500 | não | 17,0 s |

Os tempos foram medidos com a avaliação do GGUF ocupando a CPU ao mesmo tempo, menos o da última linha. Com a CPU livre, a mesma resposta levou 5,8 s em vez de 17,4 s. O erro no caso das regras não é típico: no teste, o aluno em bf16 resolveu 90,5% dos casos desse tipo.
