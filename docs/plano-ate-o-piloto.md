# Plano de implementação: da parte gratuita até o piloto

> **Para quem executar:** use superpowers:subagent-driven-development ou superpowers:executing-plans, tarefa por tarefa. Os passos usam caixas (`- [ ]`) para acompanhar o progresso.

**Objetivo:** construir o sistema de pedidos simulado, a política, os cenários, o avaliador, o loop de conversa, o formato de treino do Qwen3 e os adaptadores do Claude; provar que o treino cabe na RX 7600; e rodar o piloto de 30 conversas do professor, parando para mostrar custo e acerto.

**Arquitetura:** a política em código calcula o estado final esperado de cada cenário. O sistema simulado executa as ferramentas e guarda o estado de verdade. O avaliador compara os dois. O loop de conversa liga um agente qualquer (o Claude agora, o Qwen depois) a um cliente simulado, pelo mesmo protocolo.

**Tecnologia:** Python 3.12 do ambiente `/ssdadata/ml/.venv`, pytest, SDK `anthropic`, `python-dotenv`, transformers, peft e torch com ROCm 7.2, todos já instalados, com exceção de `anthropic` e `pytest`.

**Desenho:** [`docs/desenho.md`](desenho.md). Leia antes de começar. Este plano decide só o que o desenho deixa aberto.

## Restrições gerais

- **Ambiente:** todo comando roda com `/ssdadata/ml/.venv/bin/python`, com `HF_HOME=/mnt/hd/ml/hf-cache`.
- **Texto:** tudo em português do Brasil, incluindo identificadores, mensagens, prompts e commits.
- **Dinheiro:** sempre em centavos, como `int`. Para mostrar ao modelo, a conversão é feita por `reais(centavos)`, que devolve no formato `"R$ 23,80"`.
- **Modelos:** os IDs são exatamente `claude-opus-5-5` (professor) e `claude-haiku-5-5` (cliente simulado).
- **Sem fallback:** nenhuma chamada usa o parâmetro `fallbacks`. Uma conversa recusada é descartada, para que todas venham do mesmo professor.
- **Chave da API:** fica no `.env` (`ANTHROPIC_API_KEY`), lido com `python-dotenv`. A chave nunca é impressa, logada nem commitada.
- **Commits:** nenhum commit leva linha `Co-Authored-By`.
- **Valores da política** (copiados do desenho):
  - cupom de R$ 10 se o atraso passar de 20 minutos e de R$ 20 se passar de 45;
  - reclamação de item até 48 horas depois da entrega;
  - teto de reembolso de R$ 80, valendo "acima de", ou seja, mais de 8000 centavos;
  - transferência se o pedido estiver "a caminho" há mais de 60 minutos além da previsão;
  - uma compensação por pedido, e reembolso de itens vale mais que cupom.

## Pontos de atenção na revisão

1. **O modelo manda argumentos de tipo errado ou incompletos.** O sistema devolve `{"erro": ...}` e não quebra. Teste na Tarefa 2.
2. **Acentos nos resultados das ferramentas.** Eles chegam ao Qwen como texto (`Pão`) e não como escape (`ã`). Teste na Tarefa 6.
3. **O cliente simulado nunca encerra.** A conversa para no limite de falas. Teste na Tarefa 5.
4. **Erro passageiro da API numa conversa.** A conversa é registrada como `falha` e o lote segue. Teste na Tarefa 8.
5. **O cliente simulado pede um humano num cenário que não é `humano`.** Isso mudaria a resposta certa, então o prompt dele proíbe. Teste na Tarefa 7.

---

### Tarefa 1: Projeto, tipos e política

**Arquivos:**
- Criar: `requirements.txt`, `pytest.ini`, `tests/conftest.py`, `src/modelos.py`, `src/politica.py`, `tests/fabrica.py`, `tests/test_politica.py`

**Interfaces:**
- Produz, em `src/modelos.py`:
  - `Item(id: str, nome: str, preco: int)`, uma dataclass congelada.
  - `Pedido(id, cliente_id, restaurante, itens: list[Item], taxa: int, status: str, feito_em: datetime, previsto_em: datetime, entregue_em: datetime | None = None, estornado: bool = False)`, com a propriedade `total -> int`, que soma os itens e a taxa.
  - `STATUS = ("recebido", "em_preparo", "a_caminho", "entregue", "cancelado_restaurante", "cancelado_cliente")`.
  - `Cenario(id, semente, tipo, cliente_id, nome, agora: datetime, pedidos: list[Pedido], pedido_alvo: str | None, itens_problema: dict[str, str], estilo: str, pedido_de_outro: str | None = None)`, com `to_dict()` e `Cenario.from_dict(d)`, que fazem ida e volta por JSON com as datas em ISO.
  - `EstadoFinal(reembolsos: frozenset[tuple[str, frozenset[str]]], cupons: frozenset[tuple[str, int]], cancelamentos: frozenset[str], transferido: bool)`, uma dataclass congelada em que todos os campos são vazios ou falsos por padrão. O reembolso total é representado como `frozenset({"todos"})`.
  - `reais(centavos: int) -> str`.
- Produz, em `src/politica.py`:
  - as constantes `CUPOM_ATRASO = ((45, 2000), (20, 1000))`, `PRAZO_RECLAMACAO_H = 48`, `TETO_REEMBOLSO = 8000`, `ATRASO_TRANSFERIR_MIN = 60` e `CUPONS_PERMITIDOS = frozenset({1000, 2000})`;
  - `TIPOS`, com os 14 tipos na ordem `status, atraso, item, item_fora_prazo, item_acima_teto, nao_chegou, cancelado_restaurante, cancelar, cancelar_tarde, humano, fora_escopo, manipular, pedido_de_outro, dois_problemas`;
  - `atraso_min(p: Pedido, agora: datetime) -> int`. Se o pedido foi entregue, conta `entregue_em - previsto_em`. Se está a caminho, conta `agora - previsto_em`. Nunca é negativo.
  - `cupom_por_atraso(minutos: int) -> int`, que devolve 0 quando não há direito.
  - `esperado(c: Cenario) -> EstadoFinal`.

**Regras de `esperado`, por grupo de tipo.** `P` é o pedido alvo.

| Tipos | Estado esperado |
|---|---|
| `status` | Vazio. Se `P` está `a_caminho` com atraso acima de 60, `transferido=True` |
| `atraso` | `cupons={(P, cupom_por_atraso(atraso))}`, ou vazio se o cupom for 0 |
| `item`, `item_fora_prazo`, `item_acima_teto` | Se a entrega passou de 48 horas: vazio. Se a soma dos itens com problema passa de 8000: `transferido=True`. Senão: `reembolsos={(P, itens_problema)}` |
| `dois_problemas` | O mesmo de `item`, sem cupom: o reembolso vale mais |
| `nao_chegou` (o status é `entregue`) | `transferido=True` |
| `cancelado_restaurante` | Se já foi estornado: vazio. Se o total passa de 8000: `transferido=True`. Senão: `reembolsos={(P, {"todos"})}` |
| `cancelar`, `cancelar_tarde` | Se o status é `recebido`: `cancelamentos={P}`. Senão: vazio |
| `humano` | `transferido=True` |
| `fora_escopo`, `manipular`, `pedido_de_outro` | Vazio |

- [ ] **Passo 1: criar os arquivos de projeto.**
  - `requirements.txt` com `anthropic`, `pytest` e `python-dotenv`.
  - `pytest.ini` com `pythonpath = src` e `testpaths = tests`.
  - `tests/conftest.py`, que faz `os.environ.setdefault("HF_HOME", "/mnt/hd/ml/hf-cache")` só se essa pasta existir.
  - Rodar: `/ssdadata/ml/.venv/bin/pip install anthropic pytest`.
- [ ] **Passo 2: escrever `tests/fabrica.py`.** São construtores curtos para os testes montarem cenários à mão: `item(id, preco)`, `pedido(id, status, itens, previsto, entregue=None, ...)` e `cenario(tipo, pedidos, alvo, itens_problema={}, agora=...)`.
- [ ] **Passo 3: escrever os testes que falham.** Ficam em `tests/test_politica.py`:
  - `test_cupom_por_atraso_limites`: `cupom_por_atraso(20) == 0`, `(21) == 1000`, `(45) == 1000` e `(46) == 2000`.
  - `test_atraso_de_30_da_cupom_de_10`: o estado é `EstadoFinal(cupons=frozenset({("P1", 1000)}))`.
  - `test_item_no_prazo_reembolsa_os_itens`: dois itens com problema, entrega 3 horas antes de `agora`. O resultado é `reembolsos == {("P1", frozenset({"i1", "i2"}))}`.
  - `test_item_fora_do_prazo_nao_faz_nada`: entrega 49 horas antes, `EstadoFinal()`.
  - `test_teto_vale_acima_de_80`: itens que somam 8000 são reembolsados; itens que somam 8001 levam a `transferido=True` sem reembolso.
  - `test_nao_chegou_mas_entregue_transfere`.
  - `test_cancelado_restaurante`: sem estorno, `{("P1", frozenset({"todos"}))}`. Já estornado, `EstadoFinal()`. Total 9000, `transferido=True`.
  - `test_cancelar_so_antes_do_preparo`: `recebido` vira `cancelamentos == {"P1"}`; `em_preparo` vira `EstadoFinal()`.
  - `test_status_a_caminho`: atraso de 30 dá `EstadoFinal()`; atraso de 61 dá `transferido=True`.
  - `test_humano_transfere` e `test_tipos_sem_acao`: `fora_escopo`, `manipular` e `pedido_de_outro` dão `EstadoFinal()`.
  - `test_dois_problemas_reembolso_vence_cupom`: atraso de 50 mais um item faltando dá só o reembolso.
- [ ] **Passo 4:** rodar `pytest tests/test_politica.py -v`. Deve falhar por importação.
- [ ] **Passo 5:** implementar `src/modelos.py` e `src/politica.py` com as interfaces acima.
- [ ] **Passo 6:** rodar `pytest tests/test_politica.py -v`. Tudo deve passar.
- [ ] **Passo 7:** fazer commit com `git add requirements.txt pytest.ini src tests && git commit -m "Tipos e política de atendimento, com testes"`.

### Tarefa 2: Sistema simulado e ferramentas

**Arquivos:**
- Criar: `src/sistema.py`, `tests/test_sistema.py`

**Interfaces:**
- Consome: `modelos`, `politica` (constantes).
- Produz:
  - `NOMES = ("listar_pedidos", "detalhar_pedido", "rastrear_entrega", "reembolsar", "emitir_cupom", "cancelar_pedido", "transferir_para_humano")`.
  - `class Sistema(c: Cenario)`, com:
    - `executar(nome: str, args: dict) -> dict`;
    - `estado_final() -> EstadoFinal`;
    - os atributos `bloqueios: list[dict]` (cada um com `ferramenta`, `args` e `motivo`) e `transferido: bool`.
  - `ferramentas_anthropic() -> list[dict]`: cada ferramenta com `name`, `description` (a descrição longa, para o professor), `input_schema` (com `additionalProperties: False` e `required`) e `strict: True`.
  - `ferramentas_qwen() -> list[dict]`: o formato `{"type": "function", "function": {"name", "description", "parameters"}}`, com uma descrição curta de uma linha.
  - Argumentos: `reembolsar(pedido_id: str, itens: list[str], motivo: str)`, em que `itens == ["todos"]` é o reembolso total (itens mais taxa). `emitir_cupom(pedido_id: str, valor: number)`, com o valor em reais. `transferir_para_humano(motivo: str, resumo: str)`. As demais recebem só `pedido_id`, e `listar_pedidos` não recebe nada.
  - `rastrear_entrega` devolve `{"pedido_id", "status", "previsto_em", "entregue_em", "atraso_minutos", "agora"}`, com horários no formato `"%d/%m %H:%M"`. `atraso_minutos` vem de `politica.atraso_min` e é `None` se o pedido não saiu.

**Comportamento:**
- **Pedido que não é do cliente logado:** a resposta é `{"erro": "pedido não encontrado"}`, sem registrar bloqueio.
- **Limites rígidos:** passar de 8000, cupom fora de `CUPONS_PERMITIDOS`, segunda compensação no mesmo pedido ou cancelar fora do status `recebido`. Em todos esses casos, a resposta é `{"erro": <motivo>}` e o bloqueio é registrado.
- **Direito:** a 48 horas, o atraso real e o rastreio são decisão do agente, e o sistema não confere.

- [ ] **Passo 1: escrever os testes que falham.**
  - `test_pedido_de_outro_cliente_nao_e_encontrado`: `detalhar_pedido` e `reembolsar` devolvem `{"erro": "pedido não encontrado"}`. O estado não muda e `bloqueios == []`.
  - `test_reembolso_acima_do_teto_e_bloqueado`: itens que somam 9000. A resposta tem `"erro"`, há um bloqueio e `estado_final() == EstadoFinal()`.
  - `test_reembolso_de_8000_passa`.
  - `test_cupom_fora_da_politica_e_bloqueado`: `valor=15` é bloqueado. `valor=10` e `valor=10.0` geram `cupons == {("P1", 1000)}`.
  - `test_segunda_compensacao_e_bloqueada`: um cupom e depois um reembolso no mesmo pedido. O segundo é bloqueado.
  - `test_cancelar`: com status `em_preparo`, há bloqueio. Com `recebido`, `cancelamentos == {"P1"}`.
  - `test_reembolso_total`: `itens=["todos"]` gera `{("P1", frozenset({"todos"}))}`, e a resposta traz `valor == reais(total)`.
  - `test_item_inexistente_e_erro_sem_bloqueio`.
  - `test_args_invalidos_nao_quebram`: `reembolsar` com `{"pedido_id": 3}`, uma ferramenta `"nao_existe"` e `emitir_cupom` com `valor="R$ 10"` devolvem todos um dict com `"erro"`.
  - `test_rastrear_mostra_atraso`: entrega 32 minutos depois da previsão dá `atraso_minutos == 32`.
  - `test_ferramentas_sao_strict`: os nomes nos dois formatos são iguais a `NOMES`, e toda ferramenta tem `strict: True` e `additionalProperties: False`.
- [ ] **Passo 2:** rodar `pytest tests/test_sistema.py -v`. Deve falhar.
- [ ] **Passo 3:** implementar `src/sistema.py`. Cada ferramenta é um método, e `executar` despacha pelo nome, capturando `KeyError`, `TypeError` e `ValueError` para devolver `{"erro": ...}`.
- [ ] **Passo 4:** rodar `pytest -v`. Tudo deve passar.
- [ ] **Passo 5:** fazer commit com `git add src tests && git commit -m "Sistema de pedidos simulado com limites rígidos nas ferramentas"`.

### Tarefa 3: Gerador de cenários

**Arquivos:**
- Criar: `src/cenarios.py`, `tests/test_cenarios.py`

**Interfaces:**
- Consome: `modelos`, `politica.TIPOS`, `politica.esperado`.
- Produz:
  - as faixas de semente `TREINO = 0`, `TESTE = 1_000_000` e `PILOTO = 2_000_000`;
  - `EMPRESA: str`, o nome da empresa fictícia. Antes de fixar o nome, pesquise na web o nome com a palavra "delivery" e escolha um que não seja de app ou marca conhecida no Brasil;
  - `gerar(semente: int, tipo: str) -> Cenario`, determinístico, usando `random.Random(semente)`, com `id = f"{tipo}-{semente}"`;
  - `lote(inicio: int, n: int) -> list[Cenario]`, em que o cenário `i` tem o tipo `TIPOS[i % 14]` e a semente `inicio + i`;
  - `salvar(cenarios, caminho)` e `carregar(caminho) -> list[Cenario]`, em JSONL;
  - `objetivo_cliente(c) -> str` e `fatos_cliente(c) -> str`, textos em português para o cliente simulado. Em `nao_chegou`, os fatos dizem que o cliente não recebeu o pedido. Em `pedido_de_outro`, dizem o ID do outro pedido.

**Faixas de geração** (a critério de quem construir dentro delas):
- de 1 a 3 pedidos por cliente;
- de 1 a 5 itens por pedido, cada um de 800 a 6000 centavos;
- taxa de 0 a 999 centavos;
- nomes de clientes, restaurantes e pratos fictícios, em listas curtas em português.

**Atraso de cada tipo.** Os atrasos de `atraso` e `status` são sorteados em faixas que cobrem os dois lados de cada limite: de 5 a 15, de 25 a 40 e de 50 a 80 minutos. `item_acima_teto` força a soma dos itens com problema acima de 8000. `item_fora_prazo` força a entrega com mais de 48 horas.

- [ ] **Passo 1: escrever os testes que falham.**
  - `test_mesma_semente_mesmo_cenario`: `gerar(7, "atraso").to_dict() == gerar(7, "atraso").to_dict()`.
  - `test_lote_cobre_os_tipos_por_igual`: `lote(TESTE, 28)` tem exatamente 2 cenários de cada tipo.
  - `test_cada_tipo_cai_no_ramo_certo`, com 50 sementes por tipo, aplicando `politica.esperado`:
    - `item_fora_prazo` é sempre `EstadoFinal()`;
    - `item_acima_teto`, `humano` e `nao_chegou` têm sempre `transferido`;
    - `item` sempre tem reembolso;
    - `cancelar` sempre cancela e `cancelar_tarde` nunca cancela;
    - em `pedido_de_outro`, o ID citado nunca está entre os pedidos do cliente;
    - `atraso` tem pelo menos um caso sem cupom, um de 1000 e um de 2000.
  - `test_objetivo_e_fatos_para_todo_tipo`: os textos não ficam vazios para nenhum tipo.
  - `test_salvar_e_carregar_ida_e_volta`.
- [ ] **Passo 2:** rodar `pytest tests/test_cenarios.py -v`. Deve falhar.
- [ ] **Passo 3:** implementar `src/cenarios.py`.
- [ ] **Passo 4:** rodar `pytest -v`. Tudo deve passar.
- [ ] **Passo 5:** fazer commit com a mensagem `"Gerador de cenários com sementes fixas"`.

### Tarefa 4: Avaliador

**Arquivos:**
- Criar: `src/avaliar.py`, `tests/test_avaliar.py`

**Interfaces:**
- Consome: `politica.esperado`, `EstadoFinal`.
- Produz:
  - `Resultado(resolvido: bool, erros_graves: list[str], bloqueios: int, transferencia_certa: bool)`;
  - `avaliar(c: Cenario, estado: EstadoFinal, bloqueios: list[dict]) -> Resultado`;
  - `resumir(itens: list[tuple[str, Resultado]]) -> dict`, que recebe pares `(tipo, resultado)` e agrega por tipo e no total `n`, `resolvidos`, `erros_graves` e `bloqueios`.
- **Erro grave:** é cada reembolso, cupom ou cancelamento que está no estado e não está no esperado. Isso inclui itens errados e valor de cupom errado. Uma compensação que faltou não conta como erro grave.

- [ ] **Passo 1: escrever os testes que falham.**
  - `test_estado_igual_resolve`.
  - `test_cupom_sem_direito_e_erro_grave`: com esperado vazio e estado com cupom, `resolvido is False` e há um erro grave.
  - `test_reembolso_de_item_errado_e_erro_grave`.
  - `test_faltou_compensar_nao_e_erro_grave`: com esperado contendo um cupom e estado vazio, `resolvido is False` e `erros_graves == []`.
  - `test_bloqueio_conta_mas_nao_e_erro_grave`: com estado igual ao esperado e um bloqueio, o resultado é resolvido, com `bloqueios == 1` e nenhum erro grave.
  - `test_transferencia_certa`.
  - `test_resumir_por_tipo`.
- [ ] **Passos 2 a 5:** rodar e ver falhar, implementar, rodar `pytest -v` até passar e fazer commit com a mensagem `"Avaliador pelo estado final"`.

### Tarefa 5: Loop de conversa

**Arquivos:**
- Criar: `src/conversa.py`, `tests/test_conversa.py`

**Interfaces:**
- Consome: `Sistema`, `Cenario`.
- Produz:
  - `class Recusa(Exception)`;
  - o protocolo `Agente.passo(entrada: list[dict]) -> dict`, que devolve `{"texto": str, "chamadas": [{"id", "nome", "args"}]}`. `entrada` traz só os eventos novos desde o último passo;
  - o protocolo `Cliente.falar(texto_agente: str | None) -> str | None`. `None` como entrada pede a mensagem de abertura; `None` como saída quer dizer que o cliente encerrou;
  - os eventos, que são dicts:
    - `{"papel": "contexto", "texto"}`;
    - `{"papel": "cliente", "texto"}`;
    - `{"papel": "agente", "texto", "chamadas"}`;
    - `{"papel": "ferramenta", "id", "nome", "resultado"}`.
  - `contexto(c) -> str`, que devolve `"Cliente logado: {nome} ({cliente_id}). Agora: {dd/mm HH:MM}."`. É o primeiro evento de toda conversa;
  - `Conversa(cenario, eventos, estado: EstadoFinal, bloqueios: list[dict], motivo_fim: str)`, em que `motivo_fim` é `cliente_encerrou`, `transferido`, `limite_turnos` ou `limite_ferramentas`;
  - `rodar(c, agente, cliente, max_falas=8, max_rodadas_ferramenta=6) -> Conversa`.

**Fluxo:**
1. A abertura do cliente vai junto com o contexto no primeiro `passo`.
2. Enquanto o agente fizer chamadas, o loop executa todas no `Sistema` e devolve os resultados no próximo `passo`.
3. Uma resposta só com texto vai para o cliente.
4. Depois de `transferir_para_humano`, o agente ganha um passo final para se despedir, e a conversa acaba.
5. Uma `Recusa` sobe para quem chamou.

- [ ] **Passo 1: escrever os testes que falham**, com dois falsos: `AgenteRoteiro`, que devolve turnos de uma lista, e `ClienteRoteiro`, que devolve falas de uma lista e depois `None`.
  - `test_conversa_simples`: os papéis dos eventos são `["contexto", "cliente", "agente", "ferramenta", "agente"]` e o motivo é `cliente_encerrou`.
  - `test_transferencia_encerra`: o motivo é `transferido`, `estado.transferido` é verdadeiro e o agente deu exatamente 2 passos.
  - `test_limite_de_falas`: um cliente que nunca encerra para em 8 falas, com o motivo `limite_turnos`.
  - `test_limite_de_ferramentas`: um agente que só chama ferramentas para em 6 rodadas, com o motivo `limite_ferramentas`.
  - `test_recusa_sobe`.
- [ ] **Passos 2 a 5:** rodar e ver falhar, implementar, rodar `pytest -v` até passar e fazer commit com a mensagem `"Loop de conversa entre agente, cliente e sistema"`.

### Tarefa 6: Formato do Qwen3, script de treino e teste de memória

**Arquivos:**
- Criar: `src/formato_qwen.py`, `src/treino.py`, `tests/test_formato_qwen.py`, `docs/medicoes.md`

**Interfaces:**
- Consome: `ferramentas_qwen()` e os eventos da Tarefa 5.
- Produz:
  - `PROMPT_ALUNO: str`, com uma ou duas linhas: o papel de atendente da `EMPRESA` e a instrução de seguir a política;
  - `INICIO_AGENTE = "<|im_start|>assistant\n<think>\n\n</think>\n\n"`;
  - `prompt_sistema(tok) -> str`, que é `tok.apply_chat_template([{"role": "system", "content": PROMPT_ALUNO}], tools=ferramentas_qwen(), tokenize=False)`;
  - `renderizar(eventos, tok) -> tuple[list[int], list[int]]`, que devolve os ids e os rótulos, com `-100` fora das falas do agente;
  - `prompt_geracao(eventos, tok) -> list[int]`, a mesma renderização seguida de `INICIO_AGENTE`, para usar na inferência do próximo plano.

**Renderização.** Cada pedaço é tokenizado separadamente, com `add_special_tokens=False`, e os pedaços são concatenados. Assim, os limites dos rótulos ficam exatos.

| Evento | Texto |
|---|---|
| contexto mais a primeira fala do cliente | `"<|im_start|>user\n{contexto}\n\n{texto}<|im_end|>\n"` |
| cliente | `"<|im_start|>user\n{texto}<|im_end|>\n"` |
| agente | `INICIO_AGENTE + corpo + "<|im_end|>\n"`. O `corpo` é o texto sem espaços nas pontas, seguido de cada chamada como `"\n<tool_call>\n" + json.dumps({"name", "arguments"}, ensure_ascii=False) + "\n</tool_call>"`. Sem texto, o corpo começa direto em `<tool_call>` |
| ferramentas seguidas | Um único `"<|im_start|>user\n"` com cada resultado entre `<tool_response>\n…\n</tool_response>`, unidos por `"\n"` e terminados em `"<|im_end|>\n"` |

Os rótulos cobrem só o `corpo + "<|im_end|>"` de cada fala do agente. O raciocínio vazio fica sempre na história, igual ao que a inferência vai montar. Isso difere do template nativo de propósito, para treino e uso baterem.

**`treino.py`.** Ele adapta o `src/train_lora.py` do review-aspects-ptbr e mantém:
- o LoRA com rank 16 nas sete projeções;
- o gradient checkpointing;
- os logits só nas posições rotuladas;
- o padding em múltiplos de 32;
- o AdamW com lr 2e-4, aquecimento de 20 passos e decaimento cosseno.

Opções novas:
- `--conversas arquivo.jsonl`, uma lista de eventos por linha;
- `--falsas TOKENS`, que gera conversas falsas e realistas, repetindo uma volta (cliente, chamada, resultado com acentos, resposta) até `renderizar` passar de `TOKENS`;
- `--passos N`, um limite de passos de otimização.

No fim, ele imprime os tokens por amostra, os segundos por passo e o pico de VRAM.

- [ ] **Passo 1: escrever os testes que falham.** Eles pulam se o tokenizer não estiver no cache local, carregado com `local_files_only=True`.
  - `test_sistema_traz_ferramentas`: `prompt_sistema(tok)` começa com `"<|im_start|>system\n" + PROMPT_ALUNO` e contém `<tools>` e os 7 nomes.
  - `test_rotulos_cobrem_so_o_agente`: `tok.decode` dos ids rotulados é igual à concatenação de `corpo + "<|im_end|>"` de cada fala do agente.
  - `test_chamada_no_formato_do_qwen`: o pedaço `<tool_call>…</tool_call>` de uma chamada `rastrear_entrega` aparece de forma idêntica na saída de `tok.apply_chat_template` para uma mensagem `assistant` com `tool_calls` equivalente.
  - `test_acentos_sem_escape`: um resultado com `"Pão & Cia"` renderiza `Pão` e não `ã`.
- [ ] **Passos 2 a 4:** rodar e ver falhar, implementar `formato_qwen.py` e rodar `pytest -v` até passar.
- [ ] **Passo 5: implementar `src/treino.py` e rodar o teste de memória.** Comando: `HF_HOME=/mnt/hd/ml/hf-cache python src/treino.py --falsas 3000 --passos 20 --batch 1 --accum 1 --out runs/teste-memoria`. Passa se o pico de VRAM ficar abaixo de 7,0 GB. Repita com `--batch 2`.
- [ ] **Passo 6: o 4B, só se fizer sentido.** Se o Qwen3-4B já estiver no cache, rode o mesmo teste com `--model Qwen/Qwen3-4B --batch 1`. Se não estiver, não baixe: pergunte ao Fernando antes, porque são uns 8 GB.
- [ ] **Passo 7: anotar e fazer commit.** Anote em `docs/medicoes.md` uma tabela com modelo, batch, tokens, pico de VRAM e segundos por passo. Commit: `"Formato de treino do Qwen3 e teste de memória na RX 7600"`.

### Tarefa 7: Professor e cliente simulado no Claude

**Arquivos:**
- Criar: `src/claude.py`, `prompts/professor.md`, `prompts/cliente.md`, `tests/test_claude.py`

**Interfaces:**
- Consome: `ferramentas_anthropic()`, `Recusa`, os eventos, e `objetivo_cliente`, `fatos_cliente` e `EMPRESA`.
- Produz:
  - `PRECOS`, em dólares por milhão de tokens, na ordem entrada, saída, leitura de cache e escrita de cache:
    - `claude-opus-5-5`: `(4.00, 20.00, 0.20, 5.00)`;
    - `claude-sonnet-5-5`: `(2.00, 10.00, 0.20, 2.50)`;
    - `claude-haiku-5-5`: `(0.10, 0.50, 0.10, 0.125)`. Marque com `# ponytail:` que o preço de cache do Haiku foi aproximado pelo teto.
  - `Uso(modelo)`, com os campos `entrada`, `saida`, `cache_leitura` e `cache_escrita`, o método `somar(usage)`, que lê de `response.usage`, e o método `custo() -> float`.
  - `mensagem_usuario(entrada: list[dict]) -> dict`. Eventos de contexto e de cliente viram blocos `text`. Eventos de ferramenta viram blocos `tool_result`, com `tool_use_id=id` e `content=json.dumps(resultado, ensure_ascii=False)`.
  - `Professor(api, modelo="claude-opus-5-5", effort="low")`, que implementa `Agente` e tem o atributo `uso`.
  - `ClienteSimulado(api, c: Cenario, modelo="claude-haiku-5-5")`, que implementa `Cliente` e tem o atributo `uso`.

**Chamada do professor:** `api.messages.create` com:
- `model`;
- `max_tokens=8000`;
- `system` com o texto de `prompts/professor.md`, com `{EMPRESA}` substituído;
- `tools=ferramentas_anthropic()`;
- `tool_choice={"type": "auto"}`;
- `output_config={"effort": effort}`;
- `cache_control={"type": "ephemeral"}`;
- `messages`, a lista que ele mesmo guarda.

Depois da chamada:
- o `response.content` entra inteiro e sem mudanças como mensagem `assistant`;
- se `stop_reason` for `refusal` ou `max_tokens`, o professor levanta `Recusa`;
- o retorno é o texto junto, com as chamadas tiradas dos blocos `tool_use` (`id`, `name` e `input`).

**O cliente simulado:**
- O `system` vem de `prompts/cliente.md`, preenchido com nome, pedido alvo (restaurante e itens), `fatos_cliente`, `objetivo_cliente` e estilo.
- O histórico dele fica com os papéis invertidos: o agente fala como `user` e o cliente responde como `assistant`.
- A primeira mensagem `user` é `"(Comece a conversa.)"`.
- Usa `effort="low"`.
- Uma saída que contém `[FIM]` faz `falar` devolver `None`.

**`prompts/professor.md`:**
- descreve o papel e a política inteira, com os números do desenho;
- explica o uso de `itens=["todos"]` e a regra de resolver só o problema que o cliente trouxe;
- é escrito uma vez, antes do piloto.

**`prompts/cliente.md`:**
- respostas de 1 a 3 frases, em português informal;
- afirmar só o que está nos fatos;
- terminar com `[FIM]` quando o problema for resolvido ou quando o atendente disser que não pode fazer mais nada;
- a frase exata `Nunca peça para falar com um humano.`, presente em todo tipo, menos `humano`.

- [ ] **Passo 1: escrever os testes que falham.** Usam uma API falsa (`SimpleNamespace`), sem rede.
  - `test_custo`: 1M de entrada e 1M de saída no Opus custam US$ 24,00.
  - `test_mensagem_usuario_ferramenta`: o evento vira um bloco `tool_result`, e o JSON mantém os acentos.
  - `test_professor_guarda_resposta_inteira`: `mensagens[-1]["content"] is resposta.content`, as chamadas são extraídas e o uso é somado.
  - `test_professor_sem_fallback_e_tool_choice_auto`: os kwargs da chamada falsa não têm `fallbacks` e têm `tool_choice == {"type": "auto"}`.
  - `test_recusa`: `stop_reason="refusal"` levanta `Recusa`.
  - `test_cliente_encerra_com_fim`: as respostas falsas `"cadê meu pedido?"` e `"valeu! [FIM]"` fazem a segunda chamada de `falar` devolver `None`.
  - `test_cliente_nunca_pede_humano`: a frase proibida está no `system` para o tipo `atraso` e não está para `humano`.
  - `test_prompt_professor_tem_os_numeros`: o arquivo contém `R$ 10`, `R$ 20`, `R$ 80`, `20 minutos`, `45 minutos`, `48 horas`, `60 minutos` e `"todos"`.
- [ ] **Passos 2 a 5:** rodar e ver falhar, implementar, rodar `pytest -v` até passar e fazer commit com a mensagem `"Professor e cliente simulado no Claude, com contagem de custo"`.

### Tarefa 8: Piloto

**Arquivos:**
- Criar: `src/piloto.py`, `tests/test_piloto.py`

**Interfaces:**
- Consome: `lote`, `PILOTO`, `rodar`, `avaliar`, `resumir`, `Professor`, `ClienteSimulado` e `PRECOS`.
- Produz: `rodar_lote(cenarios, fabrica, teto_dolares: float, paralelo: int = 4) -> list[dict]`.
  - `fabrica(c)` devolve um par `(agente, cliente)`, e cada um tem `uso.custo()`.
  - Cada registro traz `cenario`, `status` (`ok`, `recusada` ou `falha`), `eventos`, `estado`, `esperado`, `resultado`, `motivo_fim`, `custo` e `uso`.
  - Antes de lançar cada conversa, o lote confere o custo acumulado e para de lançar novas quando ele chega ao teto.

**Linha de comando:** `python src/piloto.py --n 30 --inicio 2000000 --teto-dolares 10 --paralelo 4`.
1. Carrega o `.env`. Se a chave não estiver lá, sai com uma mensagem clara, sem imprimir nada da chave.
2. Grava cada conversa em `runs/piloto/<id>.json`.
3. Imprime o relatório, com números no formato brasileiro:
   - conversas ok, recusadas e com falha;
   - custo total e custo por conversa, separando professor e cliente;
   - acerto do professor no total e por tipo;
   - erros graves e tentativas bloqueadas;
   - estimativa para 1.500 e 2.000 conversas no Opus 5.5 (medida) e no Sonnet 5.5, com os mesmos tokens ao preço do Sonnet e marcada como estimativa.

- [ ] **Passo 1: escrever os testes que falham.** Usam fábricas falsas, sem rede.
  - `test_falha_e_registrada_e_o_lote_segue`: um dos agentes levanta `RuntimeError`. O status dele é `falha`, e os outros ficam `ok`.
  - `test_recusa_vira_status_recusada`.
  - `test_teto_para_de_lancar`: com custo falso de 1,0 por conversa, `teto_dolares=2.5` e `paralelo=1`, o lote roda exatamente 3 conversas.
- [ ] **Passos 2 a 4:** rodar e ver falhar, implementar e rodar `pytest -v` até passar. Depois, commit com a mensagem `"Script do piloto com teto de gasto"`.
- [ ] **Passo 5, do Fernando:**
  1. Criar o arquivo `/ssdadata/Projetos/Github/agente-suporte-ptbr/.env` num editor, com a linha `ANTHROPIC_API_KEY=...`.
  2. Definir um limite de gasto no console da Anthropic.
  3. Avisar quando terminar.

  Quem executa só confere que o arquivo existe e está no `.gitignore` (`git check-ignore .env`), sem abri-lo.
- [ ] **Passo 6:** rodar o comando do piloto.
- [ ] **Passo 7: parar e reportar.** Leia 5 conversas do piloto, incluindo as que erraram, e anote problemas de prompt ou de política, se houver. Acrescente o relatório a `docs/medicoes.md` e faça commit. Mostre ao Fernando o custo por conversa, o acerto do professor e as estimativas. Qualquer correção de prompt e um novo piloto gastam dinheiro e esperam o OK dele. A geração completa é assunto do próximo plano.
