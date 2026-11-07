"""Piloto: algumas conversas do professor para medir custo e acerto antes do gasto grande.

uso: python src/piloto.py --n 30 --inicio 2000000 --teto-dolares 10 --paralelo 4
"""
import argparse
import json
import os
import sys
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict
from pathlib import Path

from avaliar import Resultado, avaliar, resumir
from cenarios import PILOTO, lote
from claude import Uso
from conversa import Recusa, rodar
from modelos import EstadoFinal
from politica import esperado

RAIZ = Path(__file__).resolve().parent.parent


def estado_dict(e: EstadoFinal) -> dict:
    return {"reembolsos": sorted([p, sorted(i)] for p, i in e.reembolsos), "cupons": sorted([p, v] for p, v in e.cupons),
            "cancelamentos": sorted(e.cancelamentos), "transferido": e.transferido}


def _uma(c, fabrica) -> dict:
    agente, cliente = fabrica(c)
    reg = {"cenario": c.to_dict(), "status": "ok", "esperado": estado_dict(esperado(c))}
    try:
        conv = rodar(c, agente, cliente)
        reg.update(eventos=conv.eventos, estado=estado_dict(conv.estado), motivo_fim=conv.motivo_fim,
                   resultado=asdict(avaliar(c, conv.estado, conv.bloqueios)))
    except Recusa as e:
        reg.update(status="recusada", erro=str(e))
    except Exception as e:  # ponytail: uma conversa que falha não derruba o lote; o erro fica registrado
        reg.update(status="falha", erro=f"{type(e).__name__}: {e}")
    reg["uso"] = {"agente": asdict(agente.uso), "cliente": asdict(cliente.uso)}
    reg["custo"] = agente.uso.custo() + cliente.uso.custo()
    return reg


def rodar_lote(cenarios, fabrica, teto_dolares: float, paralelo: int = 4) -> list[dict]:
    """Roda as conversas em paralelo e para de lançar novas quando o gasto chega ao teto."""
    registros, gasto, fila, pendentes = [], 0.0, iter(cenarios), set()
    with ThreadPoolExecutor(paralelo) as ex:
        while True:
            while len(pendentes) < paralelo and gasto < teto_dolares and (c := next(fila, None)) is not None:
                pendentes.add(ex.submit(_uma, c, fabrica))
            if not pendentes:
                return registros
            prontos, pendentes = wait(pendentes, return_when=FIRST_COMPLETED)
            for f in prontos:
                registros.append(f.result())
                gasto += registros[-1]["custo"]


def _br(x: float, casas: int = 2) -> str:
    return f"{x:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def relatorio(registros: list[dict]) -> str:
    n = len(registros)
    ok = [r for r in registros if r["status"] == "ok"]
    contagem = {s: sum(r["status"] == s for r in registros) for s in ("ok", "recusada", "falha")}
    agente = sum(Uso(**r["uso"]["agente"]).custo() for r in registros)
    cliente = sum(Uso(**r["uso"]["cliente"]).custo() for r in registros)
    sonnet = sum(Uso(**{**r["uso"]["agente"], "modelo": "claude-sonnet-5-5"}).custo() for r in registros) + cliente
    s = resumir([(r["cenario"]["tipo"], Resultado(**r["resultado"])) for r in ok])
    t = s["total"]
    linhas = [
        f"conversas: {n} (ok {contagem['ok']}, recusadas {contagem['recusada']}, falhas {contagem['falha']})",
        f"custo: US$ {_br(agente + cliente)} no total | US$ {_br((agente + cliente) / n, 3)} por conversa "
        f"(professor {_br(agente / n, 3)} + cliente {_br(cliente / n, 3)})",
        f"acerto do professor: {t['resolvidos']}/{t['n']} ({_br(100 * t['resolvidos'] / max(t['n'], 1), 0)}%) | "
        f"erros graves: {t['erros_graves']} | tentativas bloqueadas: {t['bloqueios']} | "
        f"transferências certas: {t['transferencias_certas']}/{t['n']}",
        "por tipo:",
        *[f"  {tipo}: {d['resolvidos']}/{d['n']}" + (f", {d['erros_graves']} erro(s) grave(s)" if d["erros_graves"] else "")
          for tipo, d in sorted(s["por_tipo"].items())],
    ]
    for total in (1500, 2000):
        linhas.append(f"estimativa para {_br(total, 0)} conversas: Opus 5.5 US$ {_br(total * (agente + cliente) / n, 0)} "
                      f"(medido) | Sonnet 5.5 ~US$ {_br(total * sonnet / n, 0)} (estimativa: mesmos tokens a preço do Sonnet)")
    linhas += [f"  {r['cenario']['id']}: {r['status']}: {r.get('erro', '')}" for r in registros if r["status"] != "ok"]
    return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--inicio", type=int, default=PILOTO)
    ap.add_argument("--teto-dolares", type=float, default=10)
    ap.add_argument("--paralelo", type=int, default=4)
    ap.add_argument("--saida", default=str(RAIZ / "runs" / "piloto"))
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Falta ANTHROPIC_API_KEY no arquivo .env na raiz do repositório.")
    import anthropic
    from claude import ClienteSimulado, Professor

    api = anthropic.Anthropic(max_retries=4)
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    registros = rodar_lote(lote(args.inicio, args.n), lambda c: (Professor(api), ClienteSimulado(api, c)),
                           args.teto_dolares, args.paralelo)
    for r in registros:
        (saida / f"{r['cenario']['id']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    texto = relatorio(registros)
    (saida / "relatorio.txt").write_text(texto + "\n")
    print(texto)


if __name__ == "__main__":
    main()
