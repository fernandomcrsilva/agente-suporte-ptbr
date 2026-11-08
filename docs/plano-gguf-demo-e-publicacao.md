# Plano 3: GGUF, demo e publicação

> **Para quem executar:** use superpowers:executing-plans, a forma escolhida pelo Fernando, tarefa por tarefa. Os passos usam caixas (`- [ ]`) para acompanhar o progresso.

**Objetivo:** transformar o aluno num GGUF que roda na CPU, medir se a compactação piorou o atendimento, montar a demo em Gradio, escrever o README e os cartões e, só com o OK do Fernando, publicar tudo no GitHub e no Hugging Face.

**Arquitetura:**
- **GGUF no mesmo caminho do treino.** Um `ModeloGGUF` tem a mesma interface do `ModeloQwen` (`tok` e `gerar(ids) -> str`). Os ids continuam vindo do `prompt_geracao`, com o tokenizer do Hugging Face, e vão direto para o llama.cpp. O template de chat do llama.cpp nunca é usado, porque o aluno foi treinado num formato próprio (`formato_qwen.py`). Assim, o `AgenteQwen`, o loop e o `piloto.py` funcionam sem mudança.
- **Loop em sessão.** A demo não tem cliente simulado: quem escreve é o recrutador. Por isso, a vez do agente sai do `rodar` para uma `Sessao`, que avança uma fala do cliente por vez. O `rodar` passa a usar a `Sessao`.
- **Demo.** A lógica (casos prontos, painel e conferência) fica em `src/demo.py` e é testada sem Gradio. O `demo/app.py` só monta a tela e carrega o modelo.

**Tecnologia:** llama.cpp (conversão e quantização), llama-cpp-python (inferência na CPU), Gradio (tela) e huggingface_hub (download e publicação). As versões exatas são fixadas na execução, a partir das mais recentes que funcionarem, e anotadas em `demo/requirements.txt` e no README.

**Desenho:** [`docs/desenho.md`](desenho.md), seções "Demo" e "Limitações para escrever no README". **Planos anteriores:** [`docs/plano-ate-o-piloto.md`](plano-ate-o-piloto.md) e [`docs/plano-treino-e-avaliacao.md`](plano-treino-e-avaliacao.md).

## Restrições gerais

- **Nada sai do computador antes do OK.** Até a Tarefa 6 terminar com o OK do Fernando, nenhuma tarefa cria repositório, Space ou upload, nem privado: nada de `gh repo create`, `hf repo create` ou `hf upload`.
- **Nomes (minha escolha, o Fernando confirma na Tarefa 6):**

  | O quê | Onde |
  |---|---|
  | Código | `github.com/fernandomcrsilva/agente-suporte-ptbr` (público) |
  | Adaptador LoRA | `FMendonca/qwen3-1.7b-agente-suporte-ptbr` |
  | GGUF | `FMendonca/qwen3-1.7b-agente-suporte-ptbr-gguf`, arquivo `qwen3-1.7b-agente-suporte-ptbr-Q4_K_M.gguf` |
  | Conversas de treino | `FMendonca/conversas-suporte-delivery-ptbr` (dataset) |
  | Demo | `FMendonca/agente-suporte-ptbr` (Space, CPU gratuita) |

- **Licenças (minha escolha):** o código fica em MIT, como já está. O adaptador e o GGUF ficam em Apache 2.0, a mesma do Qwen3. As conversas ficam em CC BY 4.0, porque foram escritas pelo DeepSeek V4.1 Flash (MIT) e pelo Mistral Small 3.1 (Apache 2.0) sobre cenários sintéticos.
- **Congelado:** os `prompts/*.md`, o `src/politica.py`, as conversas de treino e o adaptador não mudam. Não há treino novo.
- **Nada do Claude publicado como dado.** O dataset é só `data/conversas/*.jsonl`, que veio de `runs/geracao`, feito com o professor aberto. As pastas `runs/` continuam fora do git.
- **Gasto:** até US$ 1 no Workers AI, para o cliente simulado na avaliação do GGUF. Nenhum gasto na Anthropic: o GGUF não passa pelo juiz.
- **Space:** só a CPU gratuita. Hardware pago só com o OK do Fernando.
- **Branch:** `demo-e-publicacao`, criado a partir da `main`. A junção na `main` faz parte do OK da Tarefa 6.
- **Trabalhos longos:** rodam com `setsid nohup`, com log em `runs/*.log`.
- **Texto e commits:** tudo em português do Brasil, escrito direto e não traduzido. Nenhum commit leva linha `Co-Authored-By`.

## Pontos de atenção na revisão

1. **Formato diferente do treino.** Se algum caminho do GGUF usar `create_chat_completion` ou o template de chat embutido no GGUF, o aluno vê um formato que nunca viu. O `ModeloGGUF` recebe ids e decodifica com o tokenizer do Hugging Face. Teste na Tarefa 1.
2. **Transferência no meio da demo.** Depois de transferir, a sessão não aceita mais falas e a caixa de texto trava. Teste nas Tarefas 3 e 4.
3. **Agente preso chamando ferramentas.** Depois de 6 rodadas seguidas de ferramenta, a sessão encerra com `limite_ferramentas` e a demo explica isso. Teste na Tarefa 3.
4. **Mensagem vazia do recrutador ou resposta vazia do agente.** Uma mensagem vazia não chama o modelo. Uma resposta vazia aparece como "(o atendente não escreveu nada)". Teste na Tarefa 4.
5. **Conversa maior que o contexto.** Se o llama.cpp recusar o prompt por passar do `n_ctx`, a demo encerra com um aviso em vez de travar. Teste na Tarefa 4.

---

### Tarefa 1: O aluno em GGUF

**Arquivos:**
- Criar: `src/gguf.py`
- Modificar: `src/aluno.py`, `tests/test_aluno.py`, `src/piloto.py` e `.gitignore` (acrescentar `.superpowers/`)

**Interfaces:**
- Produz:
  - `python src/gguf.py --adaptador runs/aluno --llama-cpp /mnt/hd/ml/llama.cpp --saida runs/gguf`, que funde o LoRA no Qwen3-1.7B em bf16 (`merge_and_unload`, na CPU), salva modelo e tokenizer em `runs/gguf/fundido`, converte com `convert_hf_to_gguf.py --outtype bf16` e quantiza com `llama-quantize` para `Q4_K_M`. O arquivo final é `runs/gguf/qwen3-1.7b-agente-suporte-ptbr-Q4_K_M.gguf`. Com `--quant Q8_0`, faz a alternativa.
  - `class ModeloGGUF(caminho: str, tokenizer: str = "Qwen/Qwen3-1.7B", n_threads: int = 2, n_ctx: int = 8192, max_novos: int = 400)` em `src/aluno.py`, com os atributos `tok` (o `AutoTokenizer` do Hugging Face) e o método `gerar(ids: list[int]) -> str`.
    - Usa a API de baixo nível do llama-cpp-python, que recebe tokens (`Llama.generate`), com temperatura 0 e `repeat_penalty=1.0`. Confira na versão instalada como passar ids e como o cache de prefixo é reaproveitado entre chamadas.
    - Para em `<|im_end|>` ou `<|endoftext|>`, ou depois de `max_novos` tokens.
    - Junta os ids gerados e decodifica com `self.tok.decode(ids, skip_special_tokens=False)`, como o `ModeloQwen`.
    - O `import llama_cpp` fica dentro do `__init__`, para o `aluno.py` continuar importável sem ele.
  - `piloto.py --agente gguf --gguf CAMINHO --threads N`, com `paralelo=1`. O `--gguf` é obrigatório com `gguf`.

- [ ] **Passo 1: montar o llama.cpp.** Clone o llama.cpp em `/mnt/hd/ml/llama.cpp`, na tag de release mais recente, e compile só o `llama-quantize` com `cmake -B build && cmake --build build --target llama-quantize -j 16`. Instale o llama-cpp-python no `/ssdadata/ml/.venv`, de preferência pela roda pronta para CPU. Anote a tag e as versões no ledger.
- [ ] **Passo 2: escrever o teste que falha.** `test_gguf_chama_ferramenta` pula se o `llama_cpp` não estiver instalado ou se o GGUF não existir. Ele roda `AgenteQwen(ModeloGGUF(GGUF), SISTEMA_ALUNO).passo(...)` com o contexto de `gerar(0, "atraso")` e a fala `"Meu pedido chegou atrasado e eu quero reclamar."`. Passa se a fala tiver pelo menos uma chamada cujo `nome` está em `sistema.NOMES`.
- [ ] **Passo 3: gerar o GGUF.** Rode `python src/gguf.py --adaptador runs/aluno --llama-cpp /mnt/hd/ml/llama.cpp --saida runs/gguf`. Esperado: um arquivo de 1,0 a 1,3 GB. Rode o teste e veja falhar, porque o `ModeloGGUF` ainda não existe.
- [ ] **Passo 4: implementar o `ModeloGGUF` e o `--agente gguf`.** Rode `pytest -q` até tudo passar.
- [ ] **Passo 5:** fazer commit com a mensagem `"Aluno em GGUF: fusão, quantização e inferência na CPU pelo mesmo formato do treino"`.

### Tarefa 2: Medir o GGUF no teste e escolher a quantização

**Arquivos:**
- Modificar: `src/tabela.py` (`ORDEM` e `NOMES` ganham `gguf`, depois de `aluno`), `docs/resultados.md` (gerado) e `docs/medicoes.md`
- Saída em `runs/teste/gguf/` e `runs/gguf-2threads/`

- [ ] **Passo 1: rodar os 300 cenários de teste.** Rode em segundo plano: `setsid nohup python src/piloto.py --agente gguf --gguf runs/gguf/qwen3-1.7b-agente-suporte-ptbr-Q4_K_M.gguf --threads 8 --inicio 1000000 --n 300 --temperatura-cliente 0 --teto-dolares 1 --saida runs/teste/gguf > runs/teste-gguf.log 2>&1 &`. Leva de 1 a 3 horas. Confira que houve no máximo 3% de falhas.
- [ ] **Passo 2: escolher a quantização.** O `Q4_K_M` fica se resolver pelo menos 81,7% dos cenários, o limite de baixo do intervalo do aluno em bf16. Abaixo disso, gere o `Q8_0`, apague `runs/teste/gguf` e rode o Passo 1 de novo com ele. O nome do arquivo e os textos da tabela e dos cartões trocam `Q4_K_M` por `Q8_0`. O nome do repositório não muda.
- [ ] **Passo 3: estimar o tempo no Space.** O Space gratuito tem 2 vCPUs. Rode 20 cenários de teste com `--threads 2 --n 20 --saida runs/gguf-2threads`, fora de `runs/teste` para não entrar na tabela. Anote a mediana do tempo por passo do agente. A meta é até 6 s por passo. Se passar disso, anote e siga: a medida que vale é a do Space de verdade, na Tarefa 7.
- [ ] **Passo 4: atualizar a tabela.**
  - Em `NOMES`, o `gguf` vira: "O aluno compactado em GGUF (Q4_K_M), rodando na CPU com llama.cpp, com 8 threads. É o modelo da demo."
  - Recontar as recusas da frase "**Recusadas:**" com a mesma conferência de antes: mais de 1.000 tokens de saída do cliente significa que a recusa veio do cliente.
  - Rodar `python src/tabela.py`.
  - A linha `gguf` sai sem nota do juiz ("—").
- [ ] **Passo 5: anotar e fazer commit.**
  - Em `docs/medicoes.md`, a seção "GGUF do aluno" registra o tamanho do arquivo, a quantização escolhida, os resolvidos contra o bf16, a mediana com 8 e com 2 threads e o gasto no Workers AI.
  - Rode `pytest -q`.
  - Commit: `"Medições do aluno em GGUF no teste"`.

### Tarefa 3: A vez do agente numa sessão

**Arquivos:**
- Modificar: `src/conversa.py`, `tests/test_conversa.py`

**Interfaces:**
- Produz:
  - `class Sessao(c: Cenario, agente: Agente, max_rodadas_ferramenta: int = 6)`, com os atributos `sistema`, `eventos` e `motivo_fim: str | None`.
    - `responder(texto_cliente: str) -> str` acrescenta a fala do cliente aos eventos. Na primeira chamada, o evento `contexto` vem antes dela.
    - Em seguida, roda o agente até ele falar com o cliente sem chamar ferramenta e devolve esse texto.
    - Se houver transferência, roda o passo de despedida, define `motivo_fim = "transferido"` e devolve a despedida.
    - Se houver 6 rodadas seguidas de ferramenta, define `motivo_fim = "limite_ferramentas"` e devolve `""`.
    - Chamada com `motivo_fim` já definido levanta `RuntimeError("atendimento encerrado")`.
  - `Sessao.conversa(motivo: str) -> Conversa`.
  - `rodar(...)` mantém a assinatura e o comportamento de hoje, agora escrito em cima da `Sessao`. O limite de falas e o encerramento pelo cliente continuam no `rodar`.

- [ ] **Passo 1: escrever os testes que falham.**
  - `test_sessao_uma_fala_por_vez`: com o roteiro `[chamada("listar_pedidos"), texto("Achei.")]`, `responder("cadê?")` devolve `"Achei."`. Os papéis dos eventos são `contexto, cliente, agente, ferramenta, agente`.
  - `test_sessao_trava_depois_de_transferir`: depois da despedida, `motivo_fim == "transferido"` e um novo `responder` levanta `RuntimeError`.
  - `test_sessao_limite_de_ferramentas`: com 6 chamadas seguidas, `motivo_fim == "limite_ferramentas"`.
- [ ] **Passos 2 a 4:** rodar e ver falhar, implementar, reescrever o `rodar` e rodar `pytest -q` até tudo passar. Os testes atuais de `test_conversa.py` passam sem mudança.
- [ ] **Passo 5:** fazer commit com a mensagem `"Loop: a vez do agente numa sessão, para a demo conversar com uma pessoa"`.

### Tarefa 4: A demo

**Arquivos:**
- Criar: `src/demo.py`, `tests/test_demo.py`, `demo/app.py`, `demo/requirements.txt` e `demo/README.md` (o cartão do Space)
- Modificar: `src/cenarios.py` (`DEMO = 3_000_000`, ao lado de `TREINO`, `TESTE` e `PILOTO`)

**Interfaces:**
- Consome: `Sessao`, `AgenteQwen`, `SISTEMA_ALUNO`, `ModeloGGUF`, `fatos_cliente`, `objetivo_cliente`, `esperado` e `avaliar`.
- Produz em `src/demo.py`:
  - `CASOS: dict[str, tuple[int, str]]`, do rótulo para a semente e o tipo, com sementes `DEMO + k`. Os rótulos e tipos são:
    - "Pedido chegou atrasado" (`atraso`);
    - "Item faltando ou errado" (`item`);
    - "Reclamação depois do prazo de 48 horas" (`item_fora_prazo`), o ponto fraco medido do aluno, de propósito;
    - "Diz que não chegou, mas o rastreio diz entregue" (`nao_chegou`);
    - "Quer cancelar o pedido" (`cancelar`);
    - "Tenta mudar as regras pelo chat" (`manipular`);
    - "Pergunta pelo pedido de outra pessoa" (`pedido_de_outro`).
  - `novo_atendimento(rotulo: str, modelo) -> Sessao`, com `AgenteQwen(modelo, SISTEMA_ALUNO)`.
  - `papel(s: Sessao) -> str`: o markdown para o recrutador. Leva "Seu papel" (de `objetivo_cliente`) e "O que aconteceu de verdade (o agente não sabe)" (de `fatos_cliente`).
  - `enviar(s: Sessao, texto: str) -> tuple[str, float]`, que devolve a resposta e os segundos que ela levou.
    - Uma mensagem vazia ou só com espaços devolve `("", 0.0)` sem chamar o modelo.
    - Uma resposta vazia vira "(o atendente não escreveu nada)".
    - Se o llama.cpp recusar o prompt por passar do contexto (`ValueError`), define `motivo_fim = "contexto_cheio"` e devolve um aviso.
  - `painel(s: Sessao) -> str`: o markdown do painel ao lado. Mostra:
    - as ferramentas chamadas, cada uma com o nome, os argumentos e o resultado, até 300 caracteres;
    - o que mudou no sistema: reembolsos (com os nomes dos itens), cupons, cancelamentos, transferência e tentativas bloqueadas.
  - `conferencia(s: Sessao) -> str`: o que a política manda (`esperado`) e "Resolvido certo: sim/não" (`avaliar`). Na tela, fica num painel fechado, com aviso de spoiler.
  - `aviso_fim(motivo: str) -> str`: uma frase por motivo (`transferido`, `limite_ferramentas` e `contexto_cheio`).
- `demo/app.py`:
  - Acrescenta `Path(__file__).resolve().parent.parent / "src"` ao `sys.path`, para funcionar no repositório e no Space, que terá a mesma estrutura.
  - O modelo vem de `os.environ.get("GGUF")` ou de `hf_hub_download` no repositório do GGUF. As threads vêm de `THREADS`, que vale 2 por padrão.
  - O modelo é carregado uma vez só. A fila usa `default_concurrency_limit=1` e cada visitante tem a sua `Sessao` num `gr.State`.
  - A tela tem um seletor de caso, o papel, o chat, a caixa de texto e um botão "Recomeçar". Ao lado ficam o painel e a conferência.
  - Cada resposta mostra o tempo que levou, em segundos. Com `motivo_fim` definido, a caixa de texto trava e o chat mostra o `aviso_fim`.
- `demo/README.md`: o cabeçalho YAML do Space (`sdk: gradio`, `app_file: demo/app.py`, `license: mit`, `models` apontando para o GGUF e `short_description`), mais um texto curto em português que aponta para o GitHub.

- [ ] **Passo 1: escrever os testes que falham.** Usam o modelo falso de `test_aluno.py`, com o tokenizer real, e pulam se não houver tokenizer.
  - `test_casos_usam_sementes_da_demo`: toda semente de `CASOS` está entre `DEMO` e `DEMO + 999`. Os tipos estão em `politica.TIPOS`.
  - `test_mensagem_vazia_nao_chama_o_modelo`: `enviar(s, "   ")` devolve `("", 0.0)` e o modelo falso não foi chamado.
  - `test_resposta_vazia_vira_aviso`.
  - `test_contexto_cheio_encerra`: um modelo falso que levanta `ValueError` deixa `motivo_fim == "contexto_cheio"`.
  - `test_painel_mostra_ferramenta_e_estado`: depois de um reembolso roteirizado, o painel contém `"reembolsar"`, o nome do item e `"R$"`.
  - `test_conferencia_diz_se_resolveu`: com o estado igual ao esperado, contém `"Resolvido certo: sim"`.
  - `test_demo_trava_depois_de_transferir`: depois de uma transferência roteirizada, `aviso_fim(s.motivo_fim)` fala em transferência.
- [ ] **Passos 2 a 4:** rodar e ver falhar, implementar o `src/demo.py` e rodar `pytest -q` até passar.
- [ ] **Passo 5: escrever o app e testar como no Space.**
  - Crie `/ssdadata/ml/.venv-demo` com o uv, só com `demo/requirements.txt` e o pytest, sem torch. Isso prova que o Space não precisa de torch.
  - Fixe as versões que funcionarem em `demo/requirements.txt`. Para o llama-cpp-python, prefira a roda pronta para CPU, com `--extra-index-url`.
  - Rode `GGUF=runs/gguf/<arquivo> /ssdadata/ml/.venv-demo/bin/python demo/app.py` em segundo plano e abra `http://localhost:7860` no navegador embutido.
  - Atenda três casos à mão: atraso, prazo de 48 horas e mudar as regras. Passa se o chat responder, o painel mudar a cada ferramenta, a conferência bater com a política e a caixa travar depois de uma transferência.
- [ ] **Passo 6:** fazer commit com a mensagem `"Demo em Gradio: o recrutador atende como cliente e vê ferramentas e estado"`.

### Tarefa 5: README e cartões

**Arquivos:**
- Criar: `README.md`, `cartoes/lora.md`, `cartoes/gguf.md` e `cartoes/dados.md`
- Modificar: `docs/decisoes.md`, que ganha a seção "Decisões do plano 3", com os nomes, as licenças, a quantização, o corte da linha do Qwen3-8B e as decisões tomadas na execução

**Regras para todo texto desta tarefa:**
- Todo número vem de `docs/resultados.md` ou de `docs/medicoes.md`. Nenhum número fica sem medida.
- O texto é escrito direto em português, sem tradução, no tom do README do review-aspects.
- Os links entre README, cartões e Space usam os nomes das Restrições gerais.

- [ ] **Passo 1: cartões.**
  - **Comum aos dois modelos:**
    - Avisam que o formato de conversa não é o template de chat nativo do Qwen3 e apontam para `formato_qwen.py` como referência.
    - Não publicam o `chat_template.jinja` nem o README gerado pelo peft em `runs/aluno`.
    - Mostram os resultados do aluno: 85,7% (IC 81,7–89,3), 19 erros graves e 45,5% em reclamações fora do prazo.
  - **Adaptador LoRA:** como carregar com o peft e montar o prompt com o código do repositório.
  - **GGUF:** o resultado da Tarefa 2 contra o bf16, o tamanho e o uso com o `ModeloGGUF`.
  - **Dataset:**
    - **Formato:** uma lista de eventos por linha (`contexto`, `cliente`, `agente` e `ferramenta`).
    - **Ausências:** as linhas não trazem os metadados do cenário, e o cartão aponta para o gerador.
    - **Origem:** quem escreveu cada parte.
    - **Contagem:** 1.874 conversas de treino e 99 de validação.
    - **Filtro:** só entraram conversas em que o professor acertou o estado final.
  - Os três cartões levam o cabeçalho YAML do Hugging Face, com licença, `language: [pt]`, `base_model` e `datasets` onde couber.
- [ ] **Passo 2: README.** Seções, nesta ordem:
  - **Em um minuto:** a tabela principal com aluno, GGUF, base, aberto e claude, e o link da demo.
  - **O que o agente faz:** as ferramentas e a política.
  - **Como se mede:** pelo estado final, com o juiz como métrica secundária.
  - **Como o aluno aprende:** o professor aberto e o motivo da Política de Uso da Anthropic.
  - **Como coube numa placa AMD de 8 GB.**
  - **Como reproduzir:** os comandos de cada etapa e as versões usadas (torch 2.14.1+rocm7.2, transformers 5.22.2, peft 0.21.2, llama.cpp e llama-cpp-python da Tarefa 1).
  - **Limitações:** as quatro do desenho e mais três:
    - a demo roda o GGUF, medido à parte na Tarefa 2;
    - o tempo do aberto inclui a espera do limite de requisições;
    - a linha do Qwen3-8B, opcional no desenho, ficou de fora.
  - **Dados, créditos e licenças.**
- [ ] **Passo 3: conferir os números.** Para cada número do README e dos cartões, ache a linha de origem em `docs/resultados.md` ou `docs/medicoes.md`. Corrija o que não bater.
- [ ] **Passo 4:** rodar `pytest -q` e fazer commit com a mensagem `"README, cartões do Hugging Face e decisões do plano 3"`.

### Revisão final

Depois da Tarefa 5, um revisor novo, no modelo mais capaz, lê o branch inteiro, como nos planos anteriores. Os pontos de atenção acima vão para ele. As correções acontecem antes da Tarefa 6.

### Tarefa 6: Conferência antes de publicar e parada

- [ ] **Passo 1: higiene, só com contagens, sem imprimir nenhum valor.** Cada contagem precisa dar 0:
  - `git log --all --format=%B | grep -ci co-authored-by`;
  - `git ls-files | grep -cE '(^|/)\.env$'`;
  - `git log --all -p | grep -cE 'sk-ant-|CLOUDFLARE_API_TOKEN=[A-Za-z0-9]'`;
  - `git ls-files .superpowers runs data | wc -l`.

  Também `pytest -q` precisa passar.
- [ ] **Passo 2: parar e pedir o OK do Fernando.** Mostre os nomes e as licenças das Restrições gerais, os arquivos que vão para cada lugar, com o tamanho, e o resultado da higiene. Pergunte se pode:
  - juntar o branch na `main`;
  - criar o repositório público no GitHub;
  - publicar os três repositórios e o Space no Hugging Face.

  Sem o OK, nada da Tarefa 7 roda.

### Tarefa 7: Publicar (só depois do OK)

- [ ] **Passo 1: juntar e enviar o código.** Junte o branch na `main` e rode `pytest -q`. Depois rode `gh repo create fernandomcrsilva/agente-suporte-ptbr --public --source . --remote origin --push`, com uma descrição em português.
- [ ] **Passo 2: Hugging Face.** Use o `hf` do `/ssdadata/ml/.venv`.
  - **Dataset:** os dois `.jsonl` e `cartoes/dados.md` como `README.md`.
  - **LoRA:** `adapter_config.json`, `adapter_model.safetensors` e `cartoes/lora.md` como `README.md`.
  - **GGUF:** o arquivo `.gguf` e `cartoes/gguf.md` como `README.md`.
- [ ] **Passo 3: Space.**
  - Crie o Space com `--space-sdk gradio`.
  - Envie `demo/README.md` e `demo/requirements.txt` para a raiz, `demo/app.py` para `demo/app.py` e `src/*.py` para `src/`.
  - Espere o build e abra o Space no navegador embutido.
  - Passa se a página abrir e um atendimento de atraso funcionar.
  - Anote o tempo de abertura depois de dormir, se der para medir, e o tempo por resposta em três atendimentos.
- [ ] **Passo 4: fechar.**
  - Anote os tempos do Space em `docs/medicoes.md` e no README.
  - Faça commit com a mensagem `"Tempos da demo no Space"` e `git push`.
  - Atualize a memória do projeto com os links publicados.

## Quanto tempo leva

- **Tarefas 1 e 2:** cerca de 1 hora de trabalho, mais 1 a 3 horas da avaliação rodando sozinha.
- **Tarefas 3 e 4:** de 2 a 3 horas.
- **Tarefa 5:** de 1 a 2 horas.
- **Tarefas 6 e 7:** cerca de 1 hora, depois do OK.
