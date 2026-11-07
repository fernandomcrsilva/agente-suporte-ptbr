# Decisões da implementação até o piloto

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
