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
