# Resultados do teste

Cada sistema atendeu os mesmos 300 cenários de teste (sementes 1.000.000 em diante), que nunca entraram no treino. Todos conversaram com o mesmo cliente simulado, o Mistral Small 3.1 com temperatura 0. Mesmo assim, o Workers AI nem sempre repete a mesma fala: a primeira fala do cliente muda em cerca de 1 a cada 10 cenários entre um teste e outro.

- **Resolvidos:** o estado final (reembolsos, cupons, cancelamentos e transferência) é igual ao que a política manda. Conversas que falharam contam como não resolvidas. O intervalo de 95% vem de bootstrap.
- **Recusadas:** a conversa parou porque a resposta de um modelo foi cortada no limite de tokens. Elas contam como não resolvidas. Neste teste, 12 das 13 vieram do cliente simulado, cuja fala passou de 1.000 tokens, e só uma veio de um agente: o Claude, que passou de 8.000.
- **Erros graves:** o agente deu algo que o cliente não tinha direito de receber.
- **Tentativas bloqueadas:** o agente tentou passar de um limite e o sistema barrou.
- **Juiz:** o Claude Sonnet 5.5 leu cada conversa às cegas, sem saber qual sistema atendeu, e deu nota só ao texto que o cliente leu.
- **Custo:** só o do agente. O cliente simulado custa o mesmo para todos e fica de fora. Os sistemas que rodam em casa, na GPU ou na CPU, aparecem com custo zero.

Os sistemas:

- **aluno:** Qwen3-1.7B com LoRA, treinado com as conversas do professor aberto, rodando na RX 7600
- **gguf:** Aluno compactado em GGUF (Q8_0), rodando na CPU com llama.cpp e 8 threads, para quem não tem GPU
- **base:** Qwen3-1.7B sem treino, com o prompt completo do professor (a política escrita), na RX 7600
- **aberto:** DeepSeek V4.1 Flash no Workers AI, o professor que gerou as conversas de treino
- **claude:** Claude Opus 5.5, só como referência (as saídas dele não entram no treino)

## Resumo

| Sistema | Resolvidos (IC 95%) | Recusadas | Erros graves | Tentativas bloqueadas | Transferências certas | Clareza / tom (juiz, 1 a 5) | Promessas sem cumprir (juiz) | Custo do agente por conversa (US$) | Tempo por fala (mediana, s) |
|---|---|---|---|---|---|---|---|---|---|
| aluno | 85,7% (81,7–89,3) | 1 | 19 | 27 | 93,7% | 4,4 / 3,9 | 9 de 299 | 0,0000 | 2,5 |
| gguf | 85,3% (81,3–89,3) | 2 | 15 | 20 | 92,3% | — | — | 0,0000 | 3,2 |
| base | 53,3% (47,7–59,0) | 7 | 0 | 3 | 80,0% | 1,8 / 1,7 | 121 de 293 | 0,0000 | 2,0 |
| aberto | 98,0% (96,0–99,3) | 1 | 0 | 0 | 98,0% | 4,7 / 4,0 | 6 de 299 | 0,0008 | 12,7 |
| claude | 99,3% (98,3–100,0) | 2 | 0 | 0 | 99,3% | 4,9 / 4,2 | 4 de 298 | 0,0271 | 1,8 |

O tempo do aberto inclui a espera do limite de 18 requisições por minuto que o próprio teste impõe ao Workers AI, com 4 conversas em paralelo. Ele mostra o ritmo do teste, não a velocidade do modelo.

### Resolvidos por tipo de cenário

| Tipo | aluno | gguf | base | aberto | claude |
|---|---|---|---|---|---|
| atraso | 86,4% | 90,9% | 31,8% | 100,0% | 100,0% |
| cancelado_restaurante | 81,0% | 81,0% | 38,1% | 100,0% | 100,0% |
| cancelar | 90,5% | 95,2% | 14,3% | 100,0% | 100,0% |
| cancelar_tarde | 100,0% | 100,0% | 100,0% | 100,0% | 100,0% |
| dois_problemas | 61,9% | 66,7% | 0,0% | 95,2% | 100,0% |
| fora_escopo | 100,0% | 100,0% | 100,0% | 100,0% | 100,0% |
| humano | 100,0% | 100,0% | 76,2% | 100,0% | 95,2% |
| item | 77,3% | 63,6% | 4,5% | 86,4% | 100,0% |
| item_acima_teto | 77,3% | 68,2% | 4,5% | 100,0% | 100,0% |
| item_fora_prazo | 45,5% | 59,1% | 100,0% | 100,0% | 100,0% |
| manipular | 90,5% | 85,7% | 85,7% | 90,5% | 95,2% |
| nao_chegou | 100,0% | 100,0% | 4,5% | 100,0% | 100,0% |
| pedido_de_outro | 100,0% | 100,0% | 95,2% | 100,0% | 100,0% |
| status | 90,9% | 86,4% | 95,5% | 100,0% | 100,0% |
