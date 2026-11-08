"""Separa as conversas geradas que podem treinar o aluno e as grava em treino e validação.

uso: python src/exportar.py runs/geracao --saida data/conversas --validacao 0.05
"""
import argparse
import json
import random
from pathlib import Path

from cenarios import TESTE
from piloto import aproveitaveis as selecionar


def limpar(eventos: list[dict]) -> list[dict]:
    """Ajusta as falas do agente para o treino.

    - Chamadas que nunca rodaram (o passo de despedida depois de transferir) saem.
    - Fala que chama ferramenta perde o texto: o cliente não vê esse texto, então o aluno aprende a chamar calado.
    """
    rodaram = {e["id"] for e in eventos if e["papel"] == "ferramenta"}
    saida = []
    for e in eventos:
        if e["papel"] == "agente":
            chamadas = [c for c in e["chamadas"] if c["id"] in rodaram]
            e = {"papel": "agente", "texto": "" if chamadas else e["texto"], "chamadas": chamadas}
            if not chamadas and not e["texto"].strip():
                continue
        saida.append(e)
    return saida


def verificar_sementes(registros: list[dict]) -> None:
    """Barra o vazamento: nenhuma conversa com semente de teste pode entrar no treino."""
    vazadas = sorted(r["cenario"]["semente"] for r in registros if r["cenario"]["semente"] >= TESTE)
    if vazadas:
        raise ValueError(f"conversas com semente de teste: {vazadas[:5]}")


def dividir(registros: list[dict], validacao: float, semente: int = 0) -> tuple[list[dict], list[dict]]:
    ids = sorted(r["cenario"]["id"] for r in registros)
    val = set(random.Random(semente).sample(ids, round(len(ids) * validacao)))
    return ([r for r in registros if r["cenario"]["id"] not in val], [r for r in registros if r["cenario"]["id"] in val])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", help="pasta com um JSON por conversa, como a saída de piloto.py")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--validacao", type=float, default=0.05)
    args = ap.parse_args()

    registros = [json.loads(p.read_text()) for p in sorted(Path(args.pasta).glob("*-*.json"))]
    bons = selecionar(registros)
    verificar_sementes(bons)
    treino, val = dividir(bons, args.validacao)
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    for nome, parte in (("treino", treino), ("validacao", val)):
        with open(saida / f"{nome}.jsonl", "w") as f:
            for r in parte:
                f.write(json.dumps(limpar(r["eventos"]), ensure_ascii=False) + "\n")
    print(f"{len(registros)} conversas, {len(bons)} aproveitáveis: {len(treino)} de treino e {len(val)} de validação "
          f"em {saida}")


if __name__ == "__main__":
    main()
