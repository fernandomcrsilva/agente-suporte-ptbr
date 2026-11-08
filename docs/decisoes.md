# Decisões da implementação

Estas são as decisões que tomei durante a execução do plano, onde o plano ou o desenho deixavam espaço. Cada uma diz o que custa se estiver errada.

## Decisões

1. **Nome da empresa: Garfo Ligeiro.** A busca na web não achou app nem marca de delivery com esse nome. Se estiver errado, basta trocar uma constante em `src/cenarios.py`.
2. **Sorteio por tipo e semente.** Os cenários usam `random.Random(f"{tipo}-{semente}")`, e não só a semente. Assim, a mesma semente em tipos diferentes não repete o mesmo cliente nem o mesmo pedido. Se estiver errado, nada quebra: só muda o sorteio.
3. **Passo final depois da transferência.** O agente ganha um último passo para se despedir. Se esse passo trouxer chamadas de ferramenta, elas ficam gravadas, mas não são executadas, porque o atendimento automático já acabou. Se estiver errado, sobra uma conversa com uma chamada solta no fim, que a conversão para treino pode cortar.
4. **Atenção eficiente do ROCm ligada por padrão no treino.** Sem ela, o passo fica duas vezes mais lento e usa 6,4 GB em vez de 4,6. Se estiver errado, nada acontece em outras GPUs, porque as variáveis só valem no ROCm.
5. **`runs/` e `data/` ficam no HD.** São links para `/mnt/hd/ml`, porque o SSD está com 94% de uso, e o `.gitignore` passou a usar `/runs` e `/data` para cobrir links. Isso não tem custo.
6. **O Qwen3-4B não foi testado.** Ele não está no cache, e o plano manda perguntar antes de baixar os 8 GB. O teste fica para depois, com o seu OK.
7. **Erros de ferramenta vão marcados como erro para o Claude.** Resultados com `erro` seguem com `is_error`, que é o que a API espera. O estado final não muda, só a forma como o professor lê o erro.
8. **O cliente simulado também pode ser descartado.** Se o Claude recusar ou cortar a resposta do cliente, a conversa é descartada. Uma fala vazia do agente vira "(O atendente não escreveu nada.)", porque a API rejeita mensagem vazia. No pior caso, uma conversa é descartada em vez de travar.
9. **Pedidos cancelados pelo restaurante ficam abaixo do teto em 80% das sementes.** Assim, o tipo testa o reembolso total que o nome promete. O teto já é testado pelo tipo `item_acima_teto`. O custo é ter menos casos de teto entre os cancelados.
10. **O piloto rodou com o código de antes das correções da revisão,** porque você pediu para seguir enquanto a revisão terminava. As conversas salvas foram reavaliadas com o avaliador corrigido (`python src/piloto.py --so-relatorio`), e o resultado não mudou. As duas conversas de cancelamento podem ter horários contraditórios.

## Decisões do treino e da avaliação (plano 2)

1. **A validação mede antes de treinar.** A perda de validação é medida no passo 0, e o log mostra a perda de treino a cada 10 passos. Isso dá a linha de base do começo. Custa uns 2 minutos a mais de treino.
2. **O aberto e o Claude rodaram o teste durante o treino,** porque não usam a GPU. Isso economizou horas sem mudar o acerto. Mas o aberto rodou com 4 conversas em paralelo sob o limite de 18 requisições por minuto, e o tempo por fala dele (12,7 s) inclui essa espera. Mantive o run, porque o acerto e o juiz valem, e a tabela explica o número numa nota. O custo é que a latência real do DeepSeek ficou sem medida.
3. **O juiz não vê a fala de um passo que chama ferramenta.** O cliente nunca lê esse texto. A exceção é a despedida depois de transferir, que o cliente lê. Se estiver errado, o juiz deixa de ver frases que nenhum cliente veria.
4. **As notas do juiz são um enum de 1 a 5 no schema**, e não `minimum` e `maximum`, porque restrições numéricas podem não valer no formato estruturado. Não tem custo.
5. **A coluna de custo mostra só o agente.** O cliente simulado custa o mesmo para todos. O custo dele está nos relatórios de cada teste.
6. **Falha e recusa contam como não resolvidas.** Senão, um sistema que cai pareceria melhor. A tabela tem uma coluna de recusadas: das 11, 10 vieram do cliente simulado, cuja fala passou de 1.000 tokens. O Qwen sem treino teve 7 delas e pode aparecer até 2,3 pontos abaixo do que seria.
7. **Os registros não guardam o agente nem a temperatura do cliente.** A temperatura 0 foi conferida nos comandos que rodaram os quatro testes. A tabela recusa comparar sistemas com cenários diferentes. O custo é que um teste futuro com outra temperatura passaria sem aviso.

## Decisões do plano 3 (GGUF, demo e publicação)

1. **Nomes e licenças.** Os modelos ficam em `FMendonca/qwen3-1.7b-agente-suporte-ptbr` (LoRA) e `FMendonca/qwen3-1.7b-agente-suporte-ptbr-gguf`, sob Apache 2.0, a licença do Qwen3. As conversas vão para `FMendonca/conversas-suporte-delivery-ptbr`, sob CC BY 4.0. A demo vai para o Space `FMendonca/agente-suporte-ptbr`. Trocar um nome depois de publicar quebra os links entre README, cartões e Space.
2. **llama-cpp-python compilado do código.** A roda pronta mais nova para CPU (0.3.19) vem ligada à musl e não carrega aqui. Usei a 0.3.36, compilada, e o llama.cpp no mesmo commit dela (`0c1e570`) para converter e quantizar. O custo é que quem quiser rodar o GGUF pelo código do projeto também compila o llama-cpp-python, o que leva alguns minutos.
3. **Q8_0 em vez de Q4_K_M.** O plano pedia o Q4_K_M se ele resolvesse pelo menos 81,7% dos 300 cenários. Parei o Q4 em 79 cenários: nos 72 em que o cliente abriu a conversa com a mesma fala, ele resolveu 55, contra 65 do aluno em bf16. Ele perdeu 12 casos que o bf16 resolvia e ganhou 2. O Q8_0 tem 1,83 GB, contra 1,11 GB, e é mais lento na CPU. O custo, se a queda fosse ruído, é um arquivo maior e mais lento do que precisava.
4. **O GGUF não passa pelo juiz.** O estado final já mostra se a compactação piorou o atendimento, e o juiz custaria cerca de US$ 1,20 na Anthropic. Na tabela, a linha do GGUF sai sem nota de texto.
5. **A demo usa sementes escolhidas por caso.** O atraso usa a semente 3.000.007, com 72 minutos de atraso e cupom de R$ 20. A 3.000.000 atrasava só 5 minutos, e a demo não mostrava nenhuma ação. A demo não é avaliação, então escolher a semente não muda nenhum número.
6. **O caso do prazo de 48 horas está na demo de propósito.** É o ponto fraco medido do aluno, e a conferência pela política mostra o erro grave quando ele reembolsa. O custo é que o recrutador pode ver o agente errar.
7. **Na CPU, a demo aquece o prompt de sistema ao abrir.** Com 2 threads, a primeira fala custava 14,9 s, quase todos lendo o prompt fixo. Agora o GGUF lê esse prompt antes de a página abrir. O custo são alguns segundos a mais na abertura.
8. **A demo roda no ZeroGPU (decisão do Fernando).** O desenho previa a CPU gratuita, mas hoje um Space Gradio em CPU exige o plano PRO, que é pago. Contas gratuitas podem ter até 2 Spaces no ZeroGPU. Lá, a demo roda o aluno em bf16 com o LoRA, o mesmo modelo avaliado. Cada visitante sem login tem 2 minutos de GPU por dia, e com login gratuito são 5. O GGUF continua publicado para quem quer rodar na CPU.
9. **A linha do Qwen3-8B sem treino ficou de fora.** Era opcional no desenho. A comparação com o mesmo Qwen3-1.7B sem treino já mostra o efeito do treino.

## Pequenos ajustes que ficaram para depois

Achados da revisão final e da leitura do piloto. Nenhum afeta o resultado do piloto.

**Antes da geração completa:**
- Às vezes o professor escreve uma nota interna antes de chamar uma ferramenta, como "Entregue hoje, dentro de 48h; só reembolso do item.". A nota entra no treino do aluno. Dá para pedir no prompt que ele não escreva nada ao chamar ferramentas, ou cortar essas notas na conversão.
- O cliente simulado repete "não sei o número do pedido". Dá para trocar a frase do prompt dele.
- O prompt do professor pode dizer explicitamente para não reembolsar só uma parte dos itens quando o total passa do teto.
- Se a primeira fala do cliente já trouxer `[FIM]`, o professor recebe um texto vazio e a conversa vira falha.

**Na conversão para treino:**
- Cortar as chamadas não executadas do passo final depois de uma transferência.

**Cosmético:**
- O relatório quebra se nenhuma conversa rodar, porque divide por zero.
- O custo por conversa inclui as recusadas e as falhas, que custam menos. Por isso ele subestima um pouco o custo de cada conversa aproveitável.
- Em `item_fora_prazo`, um terço das entregas cai antes das 8h da manhã.
- `_pedido` recebe um `cliente_id` que não usa.
- Com 30 conversas, o acerto por tipo do piloto não é confiável, porque alguns ramos da política não foram sorteados.

**Da avaliação (plano 2):**
- A recusa do cliente sai igual à do agente em `src/aberto.py`, sem o prefixo "cliente:" que o `src/claude.py` usa. Por isso, o texto da tabela traz contagens deste teste escritas à mão.
- `_liberar_gpu` roda dentro do `except`, quando o traceback ainda segura os tensores (`src/piloto.py`).
- Um `<think>` sem fechamento ou um `<|endoftext|>` chegaria ao cliente (`src/formato_qwen.py`, `src/aluno.py`). Isso não aconteceu em nenhuma das 600 conversas do aluno e do Qwen sem treino.
- O agente da API que bate o `max_tokens` vira recusa. O Qwen que bate os 400 tokens segue com o texto cortado.
- O intervalo por bootstrap dá limite superior exato perto de 100%. O intervalo de Wilson seria mais honesto nesse extremo.
- Uma conversa que vira falha ou recusa perde o estado, e um erro grave cometido antes some da contagem.
- O Qwen sem treino recebe as descrições curtas das ferramentas. A política completa no prompt já traz as regras que as descrições longas repetem.
- O relatório de um teste retomado só cobre as conversas novas.
- `_falha` grava `Uso("claude-opus-5-5")` para qualquer agente. O gasto do juiz corre entre threads sem trava. As linhas `[ferramenta _invalida]` dão ao juiz uma pista de que o modelo é fraco.
