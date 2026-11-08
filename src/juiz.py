"""Juiz do texto: o Claude Sonnet lê cada conversa do teste às cegas e dá nota à clareza e ao tom do atendente.

O acerto já vem do estado final (avaliar.py). O juiz mede o que o estado não mostra: se o atendente explicou a
decisão, se foi claro e educado e se prometeu algo que não fez. Ele não vê qual sistema atendeu nem o que era esperado.

uso: python src/juiz.py runs/teste/aberto runs/teste/aluno runs/teste/base runs/teste/claude --saida runs/juiz
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from custo import Uso

MODELO = "claude-sonnet-5-5"
RAIZ = Path(__file__).resolve().parent.parent

RUBRICA = {
    "type": "object",
    "properties": {
        "clareza": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "tom": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "explicou_decisao": {"type": "boolean"},
        "prometeu_sem_cumprir": {"type": "boolean"},
        "comentario": {"type": "string"},
    },
    "required": ["clareza", "tom", "explicou_decisao", "prometeu_sem_cumprir", "comentario"],
    "additionalProperties": False,
}

SISTEMA = """Você avalia o texto de um atendente de suporte de um app de delivery de comida.

Você recebe a conversa entre o cliente e o atendente. As linhas entre colchetes mostram o que as ferramentas do \
sistema devolveram ao atendente: o cliente não vê essas linhas. Não julgue se a decisão do atendente seguiu a política \
da empresa, isso já é medido de outro jeito. Julgue só o texto que o cliente leu:

- clareza (1 a 5): o cliente entende o que aconteceu e o que vai acontecer? 5 é claro e direto; 1 é confuso, \
contraditório ou vazio.
- tom (1 a 5): educado, empático na medida certa e sem enrolação? 5 é o tom de um bom atendente; 1 é grosseiro, \
robótico ou exagerado.
- explicou_decisao: quando o atendente concedeu, negou ou encaminhou algo, ele disse o motivo?
- prometeu_sem_cumprir: o atendente disse que fez ou faria algo (reembolso, cupom, cancelamento, transferência) que \
as ferramentas mostram que não foi feito?
- comentario: uma frase curta em português com o principal motivo das notas."""


def transcricao_para_juiz(eventos: list[dict]) -> str:
    """Só o que o cliente leu, mais o que as ferramentas devolveram. O cliente não vê a fala de um passo que chama
    ferramenta, exceto a despedida depois de transferir, que é o último evento da conversa."""
    linhas = []
    for k, e in enumerate(eventos):
        if e["papel"] == "cliente":
            linhas.append(f"Cliente: {e['texto']}")
        elif e["papel"] == "agente" and e["texto"].strip() and (not e["chamadas"] or k == len(eventos) - 1):
            linhas.append(f"Atendente: {e['texto'].strip()}")
        elif e["papel"] == "ferramenta":
            linhas.append(f"[ferramenta {e['nome']}: {json.dumps(e['resultado'], ensure_ascii=False)[:300]}]")
    return "\n".join(linhas)


def julgar(api, eventos: list[dict]) -> tuple[dict | None, Uso]:
    r = api.messages.create(
        model=MODELO, max_tokens=2000, system=SISTEMA,
        messages=[{"role": "user", "content": transcricao_para_juiz(eventos)}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": RUBRICA}})
    uso = Uso(MODELO)
    uso.somar(r.usage)
    if r.stop_reason == "refusal":
        return None, uso
    return json.loads(next(b.text for b in r.content if b.type == "text")), uso


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pastas", nargs="+", help="saídas do piloto.py, uma por sistema (runs/teste/<agente>)")
    ap.add_argument("--saida", default=str(RAIZ / "runs" / "juiz"))
    ap.add_argument("--teto-dolares", type=float, default=10)
    ap.add_argument("--paralelo", type=int, default=4)
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Falta ANTHROPIC_API_KEY no arquivo .env na raiz do repositório.")
    import anthropic
    api = anthropic.Anthropic(max_retries=4)

    fila = []
    for pasta in map(Path, args.pastas):
        destino = Path(args.saida) / pasta.name
        destino.mkdir(parents=True, exist_ok=True)
        for p in sorted(pasta.glob("*-*.json")):
            r = json.loads(p.read_text())
            if r["status"] == "ok" and not (destino / p.name).exists():  # retomável
                fila.append((destino / p.name, r))
    print(f"{len(fila)} conversas a julgar", flush=True)

    gasto = 0.0

    def uma(item):
        nonlocal gasto
        arquivo, r = item
        if gasto >= args.teto_dolares:
            return
        try:
            nota, uso = julgar(api, r["eventos"])
        except Exception as e:  # um julgamento que falha fica de fora; rodar de novo tenta outra vez
            print(f"  {arquivo.name}: {type(e).__name__}: {e}", flush=True)
            return
        gasto += uso.custo()
        arquivo.write_text(json.dumps({"id": r["cenario"]["id"], "nota": nota, "uso": asdict(uso),
                                       "custo": uso.custo()}, ensure_ascii=False, indent=1))

    with ThreadPoolExecutor(args.paralelo) as ex:
        list(ex.map(uma, fila))
    print(f"fim | gasto US$ {gasto:.2f}", flush=True)


if __name__ == "__main__":
    main()
