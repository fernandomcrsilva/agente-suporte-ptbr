"""Demo do agente de suporte: você faz o papel do cliente e vê as ferramentas e o estado do sistema.

uso local: GGUF=runs/gguf/qwen3-1.7b-agente-suporte-ptbr-Q4_K_M.gguf python demo/app.py
No Space, o GGUF vem do repositório do modelo no Hugging Face.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))  # igual no repositório e no Space

import gradio as gr  # noqa: E402

from aluno import ModeloGGUF  # noqa: E402
from demo import CASOS, aviso_fim, conferencia, enviar, novo_atendimento, painel, papel  # noqa: E402
from formato_qwen import prompt_sistema  # noqa: E402

REPO = "FMendonca/qwen3-1.7b-agente-suporte-ptbr-gguf"
ARQUIVO = "qwen3-1.7b-agente-suporte-ptbr-Q4_K_M.gguf"
GITHUB = "https://github.com/fernandomcrsilva/agente-suporte-ptbr"
INTRO = f"""# Atendente de suporte treinado em casa

Você é cliente da Garfo Ligeiro, um app de delivery fictício. Escolha um caso, leia o que aconteceu de verdade com o \
pedido e escreva como se fosse o cliente. Quem responde é um Qwen3-1.7B com LoRA, treinado numa placa de vídeo de 8 GB \
e compactado em GGUF. Ele roda aqui na CPU gratuita do Hugging Face, então cada resposta leva alguns segundos.

Ao lado aparecem as ferramentas que o agente chamou e o que mudou no sistema. [Código, medições e limitações]({GITHUB})."""


def carregar() -> ModeloGGUF:
    caminho = os.environ.get("GGUF")
    if not caminho:
        from huggingface_hub import hf_hub_download
        caminho = hf_hub_download(REPO, ARQUIVO)
    m = ModeloGGUF(caminho, n_threads=int(os.environ.get("THREADS", "2")))
    m.aquecer(m.tok(prompt_sistema(m.tok), add_special_tokens=False)["input_ids"])
    return m


MODELO = carregar()


def _segundos(x: float) -> str:
    return f"{x:.1f}".replace(".", ",") + " s"


def iniciar(rotulo):
    s = novo_atendimento(rotulo, MODELO)
    return s, papel(s), [], painel(s), conferencia(s), gr.update(value="", interactive=True)


def falar(texto, s, historico):
    if not texto.strip() or s.motivo_fim:
        return s, historico, gr.update(), painel(s), conferencia(s)
    resposta, segundos = enviar(s, texto)
    historico = historico + [{"role": "user", "content": texto},
                             {"role": "assistant", "content": f"{resposta}\n\n*respondeu em {_segundos(segundos)}*"}]
    caixa = gr.update(value="")
    if s.motivo_fim:
        historico.append({"role": "assistant", "content": f"**Fim do atendimento.** {aviso_fim(s.motivo_fim)}"})
        caixa = gr.update(value="", interactive=False, placeholder="Atendimento encerrado")
    return s, historico, caixa, painel(s), conferencia(s)


with gr.Blocks(title="Atendente de suporte treinado em casa") as app:
    gr.Markdown(INTRO)
    sessao = gr.State()
    with gr.Row():
        with gr.Column(scale=3):
            caso = gr.Dropdown(list(CASOS), value=next(iter(CASOS)), label="Caso")
            papel_md = gr.Markdown()
            chat = gr.Chatbot(label="Atendimento", height=460)
            caixa = gr.Textbox(label="Sua mensagem", placeholder="Escreva como cliente e aperte Enter")
            recomecar = gr.Button("Recomeçar")
        with gr.Column(scale=2):
            painel_md = gr.Markdown()
            with gr.Accordion("O que a política manda (spoiler)", open=False):
                conferencia_md = gr.Markdown()
    saidas = [sessao, papel_md, chat, painel_md, conferencia_md, caixa]
    app.load(iniciar, caso, saidas)
    caso.change(iniciar, caso, saidas)
    recomecar.click(iniciar, caso, saidas)
    caixa.submit(falar, [caixa, sessao, chat], [sessao, chat, caixa, painel_md, conferencia_md])

if __name__ == "__main__":
    app.queue(default_concurrency_limit=1).launch()
