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
