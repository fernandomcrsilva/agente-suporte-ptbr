from dataclasses import asdict

from custo import Uso
from tabela import ic95, tabela


def reg(i, resolvido=True, tipo="status", status="ok", modelo="local"):
    return {"cenario": {"id": f"{tipo}-{i}", "tipo": tipo}, "status": status, "custo": 0.0, "tempos_agente": [1.5],
            "resultado": {"resolvido": resolvido, "erros_graves": [], "bloqueios": 0, "transferencia_certa": True},
            "uso": {"agente": asdict(Uso(modelo)), "cliente": asdict(Uso("local"))}}


def nota(i, clareza=4, tom=5, prometeu=False):
    return {"id": f"status-{i}", "nota": {"clareza": clareza, "tom": tom, "explicou_decisao": True,
                                          "prometeu_sem_cumprir": prometeu, "comentario": ""}}


def test_ic95_extremos():
    assert ic95([True] * 10) == (1.0, 1.0)
    assert ic95([False] * 10) == (0.0, 0.0)
    baixo, alto = ic95([True, False] * 50)
    assert baixo < 0.5 < alto


def test_tabela_tem_uma_linha_por_sistema():
    texto = tabela({"aluno": [reg(1)], "base": [reg(1, resolvido=False)]}, {"aluno": [nota(1)], "base": []})
    assert "| aluno |" in texto and "| base |" in texto


def test_percentual_com_virgula():
    texto = tabela({"aluno": [reg(1), reg(2), reg(3, resolvido=False)]}, {"aluno": [nota(1), nota(2, prometeu=True)]})
    linha = next(l for l in texto.splitlines() if l.startswith("| aluno |"))
    assert "66,7%" in linha and "4,0 / 5,0" in linha and "1,5" in linha


def test_falha_conta_como_nao_resolvida():
    texto = tabela({"aluno": [reg(1), reg(2, status="falha")]}, {"aluno": []})
    linha = next(l for l in texto.splitlines() if l.startswith("| aluno |"))
    assert "50,0%" in linha


def test_recusa_sistemas_com_cenarios_diferentes():
    try:
        tabela({"aluno": [reg(1)], "base": [reg(1), reg(2)]}, {})
    except ValueError as e:
        assert "base" in str(e)
    else:
        raise AssertionError("a tabela comparou sistemas com cenários diferentes")


def test_avisa_que_tempo_do_aberto_inclui_a_espera():
    assert "espera" not in tabela({"aluno": [reg(1)]}, {})
    assert "18 requisições por minuto" in tabela({"aberto": [reg(1)]}, {})
