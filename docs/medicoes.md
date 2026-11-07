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
