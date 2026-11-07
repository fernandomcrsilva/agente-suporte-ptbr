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
from modelos import Cenario, EstadoFinal
from politica import esperado

RAIZ = Path(__file__).resolve().parent.parent


def estado_dict(e: EstadoFinal) -> dict:
    return {"reembolsos": sorted([p, sorted(i)] for p, i in e.reembolsos), "cupons": sorted([p, v] for p, v in e.cupons),
            "cancelamentos": sorted(e.cancelamentos), "transferido": e.transferido}


def estado_de_dict(d: dict) -> EstadoFinal:
    return EstadoFinal(reembolsos=frozenset((p, frozenset(i)) for p, i in d["reembolsos"]),
                       cupons=frozenset((p, v) for p, v in d["cupons"]),
                       cancelamentos=frozenset(d["cancelamentos"]), transferido=d["transferido"])


def reavaliar(registros: list[dict]) -> list[dict]:
    """Refaz o resultado das conversas salvas com a política e o avaliador atuais, sem chamar a API."""
    for r in registros:
        if r["status"] == "ok":
            c = Cenario.from_dict(r["cenario"])
            bloqueios = [{}] * r["resultado"]["bloqueios"]
            r["esperado"] = estado_dict(esperado(c))
            r["resultado"] = asdict(avaliar(c, estado_de_dict(r["estado"]), bloqueios))
    return registros


def _falha(c, erro) -> dict:
    return {"cenario": c.to_dict(), "status": "falha", "erro": erro, "custo": 0.0,
            "uso": {"agente": asdict(Uso("claude-opus-5-5")), "cliente": asdict(Uso("claude-haiku-5-5"))}}


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


def rodar_lote(cenarios, fabrica, teto_dolares: float, paralelo: int = 4, ao_terminar=None) -> list[dict]:
    """Roda as conversas em paralelo e para de lançar novas quando o gasto chega ao teto.

    `ao_terminar(registro)` é chamado assim que cada conversa termina, para nada pago se perder se o lote cair.
    """
    registros, gasto, fila, pendentes = [], 0.0, iter(cenarios), {}
    with ThreadPoolExecutor(paralelo) as ex:
        while True:
            while len(pendentes) < paralelo and gasto < teto_dolares and (c := next(fila, None)) is not None:
                pendentes[ex.submit(_uma, c, fabrica)] = c
            if not pendentes:
                return registros
            prontos, _ = wait(pendentes, return_when=FIRST_COMPLETED)
            for f in prontos:
                c = pendentes.pop(f)
                try:
                    reg = f.result()
                except Exception as e:  # a fábrica falhou antes de a conversa começar
                    reg = _falha(c, f"{type(e).__name__}: {e}")
                registros.append(reg)
                gasto += reg["custo"]
                if ao_terminar:
                    ao_terminar(reg)


FINS_DE_VERDADE = ("cliente_encerrou", "transferido")


def aproveitaveis(registros: list[dict]) -> list[dict]:
    """Conversas que podem ir para o treino: certas e terminadas de verdade, e não cortadas por limite.

    Sem isso, um cenário que pede "nada a fazer" passa como certo mesmo se o professor travou e não fez nada.
    """
    return [r for r in registros if r["status"] == "ok" and r["resultado"]["resolvido"]
            and r["motivo_fim"] in FINS_DE_VERDADE]


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
        f"aproveitáveis para treino: {len(aproveitaveis(registros))}/{n} | fim: " + ", ".join(
            f"{m} {sum(r.get('motivo_fim') == m for r in ok)}"
            for m in ("cliente_encerrou", "transferido", "limite_turnos", "limite_ferramentas")),
        "por tipo:",
        *[f"  {tipo}: {d['resolvidos']}/{d['n']}" + (f", {d['erros_graves']} erro(s) grave(s)" if d["erros_graves"] else "")
          for tipo, d in sorted(s["por_tipo"].items())],
    ]
    modelo = registros[0]["uso"]["agente"]["modelo"]
    for total in (1500, 2000):
        linha = f"estimativa para {_br(total, 0)} conversas: US$ {_br(total * (agente + cliente) / n, 0)} (medido, {modelo})"
        if modelo == "claude-opus-5-5":
            linha += f" | Sonnet 5.5 ~US$ {_br(total * sonnet / n, 0)} (estimativa: mesmos tokens a preço do Sonnet)"
        linhas.append(linha)
    linhas += [f"  {r['cenario']['id']}: {r['status']}: {r.get('erro', '')}" for r in registros if r["status"] != "ok"]
    return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--inicio", type=int, default=PILOTO)
    ap.add_argument("--teto-dolares", type=float, default=10)
    ap.add_argument("--paralelo", type=int, default=4)
    ap.add_argument("--professor", choices=("aberto", "claude"), default="aberto",
                    help="aberto: gpt-oss no Workers AI, que pode gerar dados de treino; claude: só para medir")
    ap.add_argument("--saida", default=str(RAIZ / "runs" / "piloto"))
    ap.add_argument("--so-relatorio", action="store_true",
                    help="não chama a API: reavalia as conversas já salvas em --saida e refaz o relatório")
    args = ap.parse_args()
    saida = Path(args.saida)

    if args.so_relatorio:
        registros = reavaliar([json.loads(p.read_text()) for p in sorted(saida.glob("*-*.json"))])
        texto = relatorio(registros)
        (saida / "relatorio.txt").write_text(texto + "\n")
        print(texto)
        return

    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
    if args.professor == "claude":  # só para medir: saídas do Claude não podem treinar modelos (Política de Uso)
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("Falta ANTHROPIC_API_KEY no arquivo .env na raiz do repositório.")
        import anthropic
        from claude import ClienteSimulado, Professor
        api = anthropic.Anthropic(max_retries=4)
        fabrica = lambda c: (Professor(api), ClienteSimulado(api, c))  # noqa: E731
    else:
        faltam = [v for v in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN") if not os.environ.get(v)]
        if faltam:
            sys.exit(f"Falta {' e '.join(faltam)} no arquivo .env na raiz do repositório.")
        from aberto import ClienteAberto, ProfessorAberto, WorkersAI
        api = WorkersAI(os.environ["CLOUDFLARE_ACCOUNT_ID"], os.environ["CLOUDFLARE_API_TOKEN"])
        fabrica = lambda c: (ProfessorAberto(api), ClienteAberto(api, c))  # noqa: E731
    saida.mkdir(parents=True, exist_ok=True)

    def gravar(r):
        (saida / f"{r['cenario']['id']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))

    registros = rodar_lote(lote(args.inicio, args.n), fabrica, args.teto_dolares, args.paralelo, ao_terminar=gravar)
    texto = relatorio(registros)
    (saida / "relatorio.txt").write_text(texto + "\n")
    print(texto)


if __name__ == "__main__":
    main()
