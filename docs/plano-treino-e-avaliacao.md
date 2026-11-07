# Plano 2: treino do aluno e avaliação

> **Para quem executar:** use superpowers:executing-plans, a forma escolhida pelo Fernando, tarefa por tarefa. Os passos usam caixas (`- [ ]`) para acompanhar o progresso.

**Objetivo:** treinar o aluno com as conversas do professor aberto e medir, nos 300 cenários de teste, o aluno contra o Qwen3-1.7B sem treino, o professor aberto e o Claude Opus 5.5, com uma tabela de resultados e o juiz do texto.

**Arquitetura:**
- **Aluno como agente.** O aluno entra no mesmo protocolo `Agente` do loop de conversa. Um `AgenteQwen` monta o prompt com `formato_qwen`, gera na RX 7600 e lê as chamadas `<tool_call>` da saída.
- **Avaliação.** A avaliação reaproveita o `piloto.py`, que ganha a escolha do agente. Todos os sistemas enfrentam o mesmo cliente simulado.
- **Juiz e tabela.** O juiz lê as transcrições às cegas, e a tabela junta tudo em `docs/resultados.md`.

**Tecnologia:** a mesma do plano 1. O torch, o transformers e o peft já estão no ambiente `/ssdadata/ml/.venv`, e o SDK `anthropic` é usado só no juiz e na linha de referência.

**Desenho:** [`docs/desenho.md`](desenho.md). **Plano anterior:** [`docs/plano-ate-o-piloto.md`](plano-ate-o-piloto.md). GGUF, demo e README ficam para o plano 3.

## Restrições gerais

- **Prompts congelados.** O prompt do professor, o do cliente e a política estão congelados desde o commit `ad621b7`. Nenhuma tarefa deste plano muda os arquivos `prompts/*.md` nem o `src/politica.py`.
- **Cenários de teste.** O teste usa `lote(TESTE, 300)`, com as sementes de 1.000.000 a 1.000.299. Nenhuma conversa com essas sementes entra no treino.
- **O mesmo cliente para todos.** Na avaliação, todos os sistemas conversam com o mesmo cliente simulado, o Mistral Small 3.1, com temperatura 0, para que a comparação fique justa.
- **Nada do Claude no treino.** Saídas do Claude nunca entram no treino, pela Política de Uso da Anthropic. Só `runs/geracao`, feito com o professor aberto, alimenta a exportação.
- **Gasto:** até US$ 25 dos créditos da Anthropic na avaliação (a linha do Opus e o juiz), como está no desenho. O Workers AI fica abaixo de US$ 2.
- **GPU:** agentes que rodam na GPU usam `paralelo=1`.
- **Trabalhos longos:** rodam com `setsid nohup`, com log em `runs/*.log`, para sobreviver se a sessão reiniciar.
- **Texto e commits:** tudo em português do Brasil, e nenhum commit leva linha `Co-Authored-By`.

## Pontos de atenção na revisão

1. **Saída do Qwen fora do padrão.** Uma `<tool_call>` sem fechamento, um bloco `<think>` perdido, um JSON inválido ou texto depois da chamada não podem derrubar a conversa. Viram uma chamada inválida, que o sistema responde com erro. Teste na Tarefa 1.
2. **Vazamento entre treino e teste.** A exportação recusa qualquer conversa com semente de teste. Teste na Tarefa 3.
3. **Falta de memória na GPU durante uma conversa do teste.** A conversa vira `falha`, a memória é liberada e o lote segue. Teste na Tarefa 4.
4. **Juiz que não julga às cegas.** A transcrição enviada ao juiz não leva o nome do sistema nem o estado esperado. Teste na Tarefa 6.
5. **Cliente com temperatura diferente entre sistemas.** O corpo da chamada leva `temperature: 0` quando a avaliação pede. Teste na Tarefa 4.

---

### Tarefa 1: Prompt de sistema configurável e leitura da saída do Qwen

**Arquivos:**
- Modificar: `src/formato_qwen.py`, `tests/test_formato_qwen.py`

**Interfaces:**
- Produz:
  - `prompt_sistema(tok, sistema: str = PROMPT_ALUNO) -> str`;
  - `renderizar(eventos, tok, sistema: str = PROMPT_ALUNO)`;
  - `prompt_geracao(eventos, tok, sistema: str = PROMPT_ALUNO)`;
  - `interpretar(saida: str, prefixo_id: str) -> dict`, que devolve `{"texto", "chamadas"}`.

**Regras de `interpretar`:**
- Corta tudo a partir de `<|im_end|>` e remove os blocos `<think>…</think>`.
- Cada trecho `<tool_call>…</tool_call>` vira uma chamada, e um `<tool_call>` sem fechamento no fim também conta.
- O JSON `{"name", "arguments"}` vira `{"id": f"{prefixo_id}{k}", "nome", "args"}`.
- Um JSON inválido vira `{"nome": "_invalida", "args": {"_argumentos_invalidos": bruto}}`, e o sistema responde "ferramenta desconhecida".
- O `texto` é o que sobra fora das chamadas, sem espaços nas pontas.

- [ ] **Passo 1: escrever os testes que falham.**
  - `test_interpreta_texto_puro`: `"Oi!<|im_end|>lixo"` vira `{"texto": "Oi!", "chamadas": []}`.
  - `test_interpreta_duas_chamadas`: duas chamadas viram os ids `q0`, `q1` e o texto `""`.
  - `test_chamada_sem_fechamento` e `test_think_perdido_some`.
  - `test_json_invalido_vira_chamada_invalida`.
  - `test_ida_e_volta_com_corpo`: `interpretar(corpo(evento) + "<|im_end|>", "x")` devolve o mesmo texto e as mesmas chamadas (nome e args) para os agentes de `EVENTOS`.
  - `test_sistema_configuravel` (com tokenizer): `prompt_sistema(tok, "XYZ")` começa com `"<|im_start|>system\nXYZ"`.
- [ ] **Passos 2 a 5:** rodar e ver falhar, implementar, rodar `pytest -q` até tudo passar e fazer commit com a mensagem `"Qwen: prompt de sistema configurável e leitura das chamadas na saída"`.

### Tarefa 2: O aluno como agente

**Arquivos:**
- Criar: `src/aluno.py`, `tests/test_aluno.py`
- Modificar: `src/custo.py`, que ganha `PRECOS["local"] = (0, 0, 0, 0)`

**Interfaces:**
- Consome: `prompt_geracao`, `interpretar`, `PROMPT_ALUNO` e `prompts.professor()`.
- Produz:
  - `class ModeloQwen(modelo: str = "Qwen/Qwen3-1.7B", adaptador: str | None = None, max_novos: int = 400)`, com os atributos `tok` e o método `gerar(ids: list[int]) -> str`. Ele liga as mesmas variáveis de ROCm do `treino.py`, carrega em bf16 na GPU e aplica o `PeftModel.from_pretrained` se houver adaptador. A geração é gulosa, para em `<|im_end|>` e decodifica com `skip_special_tokens=False`.
  - `class AgenteQwen(modelo, sistema: str)`, que implementa `Agente`:
    - tem os atributos `eventos` (a história completa, com o contexto) e `uso = Uso("local")`;
    - em cada `passo`, acrescenta a entrada, gera, interpreta com o prefixo `f"q{n}_"`, acrescenta a fala do agente e devolve o turno.
  - `SISTEMA_ALUNO = PROMPT_ALUNO` e `sistema_completo() -> str`, que devolve `prompts.professor()`, o prompt do Qwen sem treino.

- [ ] **Passo 1: escrever os testes que falham.** Usam um modelo falso, com o tokenizer real e um `gerar` roteirizado, sem GPU, e pulam se não houver tokenizer.
  - `test_aluno_conversa_com_ferramenta`: o `rodar` com `ClienteRoteiro(["cadê?"])` e as saídas roteirizadas `'<tool_call>\n{"name": "listar_pedidos", "arguments": {}}\n</tool_call><|im_end|>'` e `'Achei.<|im_end|>'` termina em `cliente_encerrou`, com a ferramenta executada.
  - `test_segunda_geracao_ve_o_resultado`: o decode dos ids da segunda chamada de `gerar` contém `<tool_response>` e o nome da chamada anterior.
  - `test_sistema_escolhido_vai_no_prompt`: com `sistema_completo()`, o decode do prompt contém `R$ 80`. Com `SISTEMA_ALUNO`, não contém.
- [ ] **Passos 2 a 4:** rodar e ver falhar, implementar e rodar `pytest -q` até passar.
- [ ] **Passo 5: conferência na GPU.** Rode `python src/aluno.py`. O `__main__` roda uma conversa roteirizada com o Qwen3-1.7B sem treino e imprime os eventos. Passa se terminar sem exceção, com uma chamada ou um texto em português.
- [ ] **Passo 6:** fazer commit com a mensagem `"Aluno como agente: Qwen3 local no protocolo do loop"`.

### Tarefa 3: Exportar e treinar de verdade

**Arquivos:**
- Modificar: `src/exportar.py`, `tests/test_exportar.py`, `src/treino.py` e `docs/medicoes.md`

**Interfaces:**
- Produz:
  - `verificar_sementes(registros) -> None`, que levanta `ValueError` se alguma `cenario.semente` for maior ou igual a `TESTE`. O `main` do exportar chama essa função antes de gravar.
  - `treino.py --validacao arquivo.jsonl`, que calcula a perda de validação a cada 50 passos e no fim, com batch 2 e sem embaralhar.

- [ ] **Passo 1: escrever o teste que falha.** `test_recusa_semente_de_teste`: um registro com `semente=1_000_005` levanta `ValueError`, e um com `semente=5` passa. O ajudante `registro()` dos testes ganha a semente.
- [ ] **Passos 2 a 4:** rodar e ver falhar, implementar e rodar `pytest -q` até passar. Também implementar a validação no `treino.py`. Fazer commit.
- [ ] **Passo 5: esperar a geração terminar** (`runs/geracao.log`). Exporte com `python src/exportar.py runs/geracao --saida data/conversas --validacao 0.05`. Passa se 90% ou mais das 2.000 conversas forem aproveitáveis. Se forem menos, pare e conte ao Fernando antes de treinar.
- [ ] **Passo 6: treinar em segundo plano.** Comando: `setsid nohup python src/treino.py --conversas data/conversas/treino.jsonl --validacao data/conversas/validacao.jsonl --out runs/aluno --epochs 2 --batch 2 --accum 8 > runs/treino.log 2>&1 &`. Passa se:
  - a perda de validação cair entre a primeira e a última medida;
  - o pico de VRAM ficar abaixo de 7 GB;
  - o adaptador for salvo em `runs/aluno`.

  O treino leva de 3 a 5 horas.
- [ ] **Passo 7: anotar e fazer commit.** Anote em `docs/medicoes.md` o número de conversas, a perda de validação no começo e no fim, o tempo total e o pico de VRAM. Commit: `"Treino do aluno com as conversas do professor aberto"`.

### Tarefa 4: Escolha do agente na avaliação

**Arquivos:**
- Modificar: `src/piloto.py`, `src/aberto.py`, `tests/test_piloto.py` e `tests/test_aberto.py`

**Interfaces:**
- Produz:
  - `piloto.py --agente {aberto,claude,aluno,base}`, que substitui `--professor`, e `--adaptador CAMINHO`, obrigatório com `aluno`.
  - O cliente é sempre o `ClienteAberto`, também para o `claude`. Com `aluno` e `base`, o paralelismo vira 1.
  - O `ModeloQwen` é carregado uma vez só e compartilhado pela fábrica.
  - `--temperatura-cliente FLOAT`, que vai para `ClienteAberto(api, c, temperatura=...)`. Quando não é `None`, o corpo da chamada leva `"temperature"`.
  - Em `_uma`, o `agente.passo` é cronometrado, e o registro ganha `tempos_agente: list[float]`.
  - Se `rodar` levantar uma exceção com `"out of memory"` na mensagem, chama `torch.cuda.empty_cache()` (importado só nesse caso) antes de registrar a `falha`.
  - O `relatorio` ganha a linha `tempo por fala do agente: mediana X s`.

- [ ] **Passo 1: escrever os testes que falham.**
  - `test_tempos_por_passo`: o agente falso dá 2 passos, então `len(r["tempos_agente"]) == 2`.
  - `test_relatorio_mostra_tempo`.
  - `test_falta_de_memoria_vira_falha_e_segue`: um agente que levanta `RuntimeError("CUDA out of memory")` vira `falha`, e o próximo fica `ok`.
  - `test_cliente_com_temperatura`: com `temperatura=0`, o corpo traz `temperature == 0`. Sem ela, não traz a chave.
- [ ] **Passos 2 a 5:** rodar e ver falhar, implementar, rodar `pytest -q` até tudo passar e fazer commit com a mensagem `"Avaliação: escolha do agente, cliente único e tempo por fala"`.

### Tarefa 5: Rodar o teste nos quatro sistemas

**Arquivos:**
- Saída em `runs/teste/<agente>/`, sem código novo.

Os comandos usam `--inicio 1000000 --n 300 --temperatura-cliente 0`. Cada um roda em segundo plano, com `setsid nohup` e log em `runs/teste-<agente>.log`. Ao fim de cada um, confira no relatório que houve no máximo 3% de falhas. Acima disso, investigue antes do próximo.

- [ ] **Passo 1: professor aberto.** `--agente aberto --paralelo 4 --teto-dolares 3`. Leva cerca de 1 hora por causa do limite de 18 por minuto.
- [ ] **Passo 2: aluno.** `--agente aluno --adaptador runs/aluno --teto-dolares 1`. Leva de 1 a 2 horas na GPU.
- [ ] **Passo 3: Qwen sem treino.** `--agente base --teto-dolares 1`, com o prompt completo do professor.
- [ ] **Passo 4: Claude Opus 5.5.** `--agente claude --paralelo 4 --teto-dolares 15`. Custa cerca de US$ 10, dentro do orçamento do desenho.
- [ ] **Passo 5: conferir e anotar.** Leia 3 conversas do aluno, incluindo uma errada, e anote o que viu em `docs/medicoes.md`. Commit.

### Tarefa 6: Juiz do texto

**Arquivos:**
- Criar: `src/juiz.py`, `tests/test_juiz.py`

**Interfaces:**
- Produz:
  - `transcricao_para_juiz(eventos) -> str`. É determinística, com as linhas `Cliente: …`, `Atendente: …` e `[ferramenta <nome>: <resultado em JSON, até 300 caracteres>]`. Não leva o contexto do sistema, o nome do agente nem o estado esperado.
  - `RUBRICA`, um schema JSON com:
    - `clareza` e `tom`, inteiros de 1 a 5;
    - `explicou_decisao` e `prometeu_sem_cumprir`, booleanos;
    - `comentario`, um texto curto.

    O schema usa `additionalProperties: False` e todos os campos são obrigatórios.
  - `julgar(api, eventos) -> tuple[dict | None, Uso]`, que chama:
    - `model="claude-sonnet-5-5"`;
    - `max_tokens=2000`;
    - `output_config={"effort": "low", "format": {"type": "json_schema", "schema": RUBRICA}}`;
    - um `system` em português que explica a rubrica e diz que o atendente é de um app de delivery.

    Lê o JSON do primeiro bloco de texto e devolve `None` se o `stop_reason` for `refusal`.
  - A linha de comando é `python src/juiz.py runs/teste/<agente> … --saida runs/juiz --teto-dolares 10`. Ela grava `runs/juiz/<agente>/<id>.json`, pula os que já existem e julga só as conversas `ok`.

- [ ] **Passo 1: escrever os testes que falham.** Usam uma API falsa.
  - `test_transcricao_e_cega`: o texto não contém `"Cliente logado"`, `"aluno"`, `"esperado"` nem o nome do modelo.
  - `test_juiz_pede_json_com_a_rubrica`: os kwargs trazem `model == "claude-sonnet-5-5"` e `output_config["format"]["schema"] == RUBRICA`.
  - `test_juiz_le_o_json` e `test_recusa_vira_none`.
- [ ] **Passos 2 a 4:** rodar e ver falhar, implementar e rodar `pytest -q` até passar.
- [ ] **Passo 5: julgar os quatro sistemas.** Rode `python src/juiz.py runs/teste/aberto runs/teste/aluno runs/teste/base runs/teste/claude --saida runs/juiz --teto-dolares 10`. São cerca de 1.200 julgamentos, por uns US$ 10.
- [ ] **Passo 6:** fazer commit com a mensagem `"Juiz do texto às cegas"`.

### Tarefa 7: Tabela de resultados

**Arquivos:**
- Criar: `src/tabela.py`, `tests/test_tabela.py` e `docs/resultados.md` (gerado)

**Interfaces:**
- Consome: `piloto.reavaliar`, `avaliar.resumir` e os JSONs do juiz.
- Produz:
  - `ic95(acertos: list[bool], reamostras: int = 1000, semente: int = 0) -> tuple[float, float]`, com bootstrap.
  - `tabela(sistemas: dict[str, list[dict]], juiz: dict[str, list[dict]]) -> str`, em markdown, com números no formato brasileiro.
    - A primeira tabela tem as colunas: Sistema, Resolvidos (% e IC 95%), Erros graves, Tentativas bloqueadas, Transferências certas (%), Clareza e tom (média do juiz), Promessas sem cumprir, Custo por conversa (US$) e Tempo por fala (mediana em segundos).
    - A segunda tabela mostra os resolvidos (%) por tipo de cenário e por sistema.
  - `python src/tabela.py` lê `runs/teste/*` e `runs/juiz/*` e grava `docs/resultados.md`.

- [ ] **Passo 1: escrever os testes que falham.**
  - `test_ic95_extremos`: `ic95([True] * 10) == (1.0, 1.0)`.
  - `test_tabela_tem_uma_linha_por_sistema`: com dois sistemas falsos, `"| aluno |"` e `"| base |"` aparecem.
  - `test_percentual_com_virgula`: 2 de 3 resolvidos aparecem como `66,7%`.
- [ ] **Passos 2 a 4:** rodar e ver falhar, implementar e rodar `pytest -q` até passar.
- [ ] **Passo 5: gerar e revisar.** Rode `python src/tabela.py`. Confira à mão um número de cada coluna contra os relatórios do `piloto.py`.
- [ ] **Passo 6:** fazer commit com a mensagem `"Tabela de resultados do teste"`.

### Revisão final

Depois da Tarefa 7, um revisor novo, no modelo mais capaz, lê o branch inteiro, como no plano 1. Os pontos de atenção acima vão para ele.
