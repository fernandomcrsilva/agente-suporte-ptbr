"""Junta o teste dos quatro sistemas e as notas do juiz em `docs/resultados.md`.

uso: python src/tabela.py
"""
import json
import random
import statistics
from pathlib import Path

from avaliar import Resultado, resumir
from custo import Uso
from piloto import _br, reavaliar

RAIZ = Path(__file__).resolve().parent.parent
ORDEM = ("aluno", "base", "aberto", "claude")
NOMES = {
    "aluno": "Qwen3-1.7B com LoRA, treinado com as conversas do professor aberto, rodando na RX 7600",
    "base": "Qwen3-1.7B sem treino, com o prompt completo do professor (a política escrita), na RX 7600",
    "aberto": "DeepSeek V4.1 Flash no Workers AI, o professor que gerou as conversas de treino",
    "claude": "Claude Opus 5.5, só como referência (as saídas dele não entram no treino)",
}


def ic95(acertos: list[bool], reamostras: int = 1000, semente: int = 0) -> tuple[float, float]:
    """Intervalo de 95% da taxa de acerto por bootstrap."""
    rng, n = random.Random(semente), len(acertos)
    medias = sorted(sum(rng.choices(acertos, k=n)) / n for _ in range(reamostras))
    return medias[int(0.025 * reamostras)], medias[int(0.975 * reamostras) - 1]


def _pct(x: float) -> str:
    return f"{_br(100 * x, 1)}%"


def _linha(nome: str, regs: list[dict], notas: list[dict]) -> str:
    n = len(regs)
    ok = [r for r in regs if r["status"] == "ok"]
    resolvidos = [r["status"] == "ok" and r["resultado"]["resolvido"] for r in regs]  # falha conta como erro
    t = resumir([(r["cenario"]["tipo"], Resultado(**r["resultado"])) for r in ok])["total"]
    baixo, alto = ic95(resolvidos)
    validas = [x["nota"] for x in notas if x["nota"]]
    juiz = (f"{_br(statistics.mean(v['clareza'] for v in validas), 1)} / "
            f"{_br(statistics.mean(v['tom'] for v in validas), 1)}") if validas else "—"
    promessas = f"{sum(v['prometeu_sem_cumprir'] for v in validas)} de {len(validas)}" if validas else "—"
    custo = sum(Uso(**r["uso"]["agente"]).custo() for r in regs) / n
    tempos = [t for r in ok for t in r.get("tempos_agente", [])]
    tempo = _br(statistics.median(tempos), 1) if tempos else "—"
    return (f"| {nome} | {_pct(sum(resolvidos) / n)} ({_br(100 * baixo, 1)}–{_br(100 * alto, 1)}) | "
            f"{t['erros_graves']} | {t['bloqueios']} | {_pct(t['transferencias_certas'] / n)} | {juiz} | "
            f"{promessas} | {_br(custo, 4)} | {tempo} |")


def tabela(sistemas: dict[str, list[dict]], juiz: dict[str, list[dict]]) -> str:
    nomes = [s for s in ORDEM if s in sistemas] + sorted(set(sistemas) - set(ORDEM))
    ids = {s: {r["cenario"]["id"] for r in sistemas[s]} for s in nomes}
    diferentes = [s for s in nomes if ids[s] != ids[nomes[0]]]
    if diferentes:  # um teste pela metade ou com outras sementes não entra na comparação
        raise ValueError(f"cenários diferentes de {nomes[0]} em: {', '.join(diferentes)}")
    linhas = [
        "| Sistema | Resolvidos (IC 95%) | Erros graves | Tentativas bloqueadas | Transferências certas | "
        "Clareza / tom (juiz, 1 a 5) | Promessas sem cumprir (juiz) | Custo do agente por conversa (US$) | "
        "Tempo por fala (mediana, s) |",
        "|---|---|---|---|---|---|---|---|---|",
        *[_linha(s, sistemas[s], juiz.get(s, [])) for s in nomes],
        "",
        *(["O tempo do aberto inclui a espera do limite de 18 requisições por minuto que o próprio teste impõe ao "
           "Workers AI, com 4 conversas em paralelo. Ele mostra o ritmo do teste, não a velocidade do modelo.", ""]
          if "aberto" in nomes else []),
        "### Resolvidos por tipo de cenário",
        "",
        "| Tipo | " + " | ".join(nomes) + " |",
        "|---|" + "---|" * len(nomes),
    ]
    tipos = sorted({r["cenario"]["tipo"] for regs in sistemas.values() for r in regs})
    for tipo in tipos:
        celulas = []
        for s in nomes:
            do_tipo = [r for r in sistemas[s] if r["cenario"]["tipo"] == tipo]
            certos = sum(r["status"] == "ok" and r["resultado"]["resolvido"] for r in do_tipo)
            celulas.append(_pct(certos / len(do_tipo)) if do_tipo else "—")
        linhas.append(f"| {tipo} | " + " | ".join(celulas) + " |")
    return "\n".join(linhas)


def main():
    teste, juiz_dir = RAIZ / "runs" / "teste", RAIZ / "runs" / "juiz"
    sistemas = {p.name: reavaliar([json.loads(f.read_text()) for f in sorted(p.glob("*-*.json"))])
                for p in sorted(teste.iterdir()) if p.is_dir()}
    juiz = {p.name: [json.loads(f.read_text()) for f in sorted(p.glob("*-*.json"))]
            for p in sorted(juiz_dir.iterdir()) if p.is_dir()} if juiz_dir.exists() else {}
    n = {s: len(r) for s, r in sistemas.items()}
    texto = "\n".join([
        "# Resultados do teste",
        "",
        f"Cada sistema atendeu os mesmos {max(n.values())} cenários de teste (sementes 1.000.000 em diante), que "
        "nunca entraram no treino. Todos conversaram com o mesmo cliente simulado, o Mistral Small 3.1 com "
        "temperatura 0.",
        "",
        "- **Resolvidos:** o estado final (reembolsos, cupons, cancelamentos e transferência) é igual ao que a "
        "política manda. Conversas que falharam contam como não resolvidas. O intervalo de 95% vem de bootstrap.",
        "- **Erros graves:** o agente deu algo que o cliente não tinha direito de receber.",
        "- **Tentativas bloqueadas:** o agente tentou passar de um limite e o sistema barrou.",
        "- **Juiz:** o Claude Sonnet 5.5 leu cada conversa às cegas, sem saber qual sistema atendeu, e deu nota só ao "
        "texto que o cliente leu.",
        "- **Custo:** só o do agente. O cliente simulado custa o mesmo para todos e fica de fora. Os sistemas na GPU "
        "local aparecem com custo zero.",
        "",
        "Os sistemas:",
        "",
        *[f"- **{s}:** {NOMES.get(s, s)}" for s in [x for x in ORDEM if x in sistemas]],
        "",
        "## Resumo",
        "",
        tabela(sistemas, juiz),
        "",
    ])
    (RAIZ / "docs" / "resultados.md").write_text(texto)
    print(texto)


if __name__ == "__main__":
    main()
