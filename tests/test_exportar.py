import json

import pytest

from exportar import dividir, limpar, para_hub, selecionar, verificar_sementes


def registro(id, resolvido=True, fim="cliente_encerrou", status="ok", eventos=None, semente=0):
    return {"cenario": {"id": id, "semente": semente}, "status": status, "motivo_fim": fim, "resultado": {"resolvido": resolvido},
            "eventos": eventos or [{"papel": "cliente", "texto": "oi"}, {"papel": "agente", "texto": "Olá!", "chamadas": []}]}


CHAMADA = {"id": "c1", "nome": "listar_pedidos", "args": {}}


def test_seleciona_so_as_aproveitaveis():
    regs = [registro("a"), registro("b", resolvido=False), registro("c", fim="limite_turnos"),
            registro("d", status="falha"), registro("e", fim="transferido")]
    assert [r["cenario"]["id"] for r in selecionar(regs)] == ["a", "e"]


def test_fala_com_chamada_perde_o_texto():
    ev = limpar([{"papel": "cliente", "texto": "oi"},
                 {"papel": "agente", "texto": "Vou ver.", "chamadas": [CHAMADA]},
                 {"papel": "ferramenta", "id": "c1", "nome": "listar_pedidos", "resultado": {}},
                 {"papel": "agente", "texto": "Achei.", "chamadas": []}])
    assert ev[1] == {"papel": "agente", "texto": "", "chamadas": [CHAMADA]}
    assert ev[3]["texto"] == "Achei."


def test_corta_chamadas_que_nao_rodaram_no_fim():
    base = [{"papel": "cliente", "texto": "quero um humano"},
            {"papel": "agente", "texto": "", "chamadas": [CHAMADA]},
            {"papel": "ferramenta", "id": "c1", "nome": "listar_pedidos", "resultado": {}}]
    ev = limpar(base + [{"papel": "agente", "texto": "Transferi.", "chamadas": [dict(CHAMADA, id="c2")]}])
    assert ev[-1] == {"papel": "agente", "texto": "Transferi.", "chamadas": []}
    ev = limpar(base + [{"papel": "agente", "texto": "", "chamadas": [dict(CHAMADA, id="c2")]}])
    assert ev[-1]["papel"] == "ferramenta"


def test_divide_sem_repetir_e_sempre_igual():
    regs = [registro(str(i)) for i in range(100)]
    treino, val = dividir(regs, 0.1)
    assert len(val) == 10 and len(treino) == 90
    assert not {r["cenario"]["id"] for r in treino} & {r["cenario"]["id"] for r in val}
    assert dividir(regs, 0.1) == (treino, val)


def test_recusa_semente_de_teste():
    verificar_sementes([registro("a", semente=5)])
    with pytest.raises(ValueError, match="1000005"):
        verificar_sementes([registro("a", semente=5), registro("b", semente=1_000_005)])


def test_para_hub_embrulha_cada_conversa(tmp_path):
    origem, destino = tmp_path / "conversas", tmp_path / "hub"
    origem.mkdir()
    conversa = [{"papel": "cliente", "texto": "oi"}, {"papel": "agente", "texto": "Olá!", "chamadas": []}]
    (origem / "treino.jsonl").write_text(json.dumps(conversa) + "\n" + json.dumps(conversa) + "\n")
    (origem / "validacao.jsonl").write_text(json.dumps(conversa) + "\n")
    assert para_hub(origem, destino) == {"treino": 2, "validacao": 1}
    linhas = (destino / "treino.jsonl").read_text().splitlines()
    assert [json.loads(l) for l in linhas] == [{"eventos": conversa}] * 2
