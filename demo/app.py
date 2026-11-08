"""Demo do agente de suporte: você faz o papel do cliente e vê as ferramentas e o estado do sistema.

No Space (ZeroGPU), roda o aluno em bf16 com o LoRA publicado no Hugging Face, o mesmo modelo avaliado.

uso local na GPU: ADAPTADOR=runs/aluno python demo/app.py
uso local na CPU: GGUF=runs/gguf/qwen3-1.7b-agente-suporte-ptbr-Q8_0.gguf python demo/app.py
"""
import os
import sys
from pathlib import Path

try:
    import spaces  # antes do torch: no ZeroGPU, ele empresta a GPU só durante cada geração
    na_gpu = spaces.GPU(duration=30)
except ImportError:  # teste local sem o pacote spaces
    def na_gpu(f):
        return f

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))  # igual no repositório e no Space

import gradio as gr  # noqa: E402

from aluno import ModeloGGUF, ModeloQwen  # noqa: E402
from demo import CASOS, aviso_fim, conferencia, enviar, novo_atendimento, painel, papel  # noqa: E402
from formato_qwen import prompt_sistema  # noqa: E402

REPO_LORA = "FMendonca/qwen3-1.7b-agente-suporte-ptbr"
GITHUB = "https://github.com/fernandomcrsilva/agente-suporte-ptbr"
INTRO = f"""# Atendente de suporte treinado em casa

Você é cliente da Garfo Ligeiro, um app de delivery fictício. Escolha um caso, leia o que aconteceu de verdade com o \
pedido e escreva como se fosse o cliente. Quem responde é um Qwen3-1.7B com LoRA, treinado numa placa de vídeo de 8 GB. \
É o mesmo modelo medido nos 300 cenários de teste, onde resolveu 85,7% dos casos. O caso do prazo de 48 horas é onde ele \
mais erra (45,5%), e está aqui de propósito.

Ao lado aparecem as ferramentas que o agente chamou e o que mudou no sistema. [Código, medições e limitações]({GITHUB})."""


class ModeloNaGPU:
    """O aluno em bf16 com o LoRA, o modelo avaliado. Cada geração pede a GPU ao ZeroGPU: entram ids e sai texto."""

    def __init__(self, adaptador: str):
        self.qwen = ModeloQwen(adaptador=adaptador)
        self.tok = self.qwen.tok

    def gerar(self, ids: list[int]) -> str:
        return _gerar_na_gpu(ids)


@na_gpu
def _gerar_na_gpu(ids: list[int]) -> str:
    return MODELO.qwen.gerar(ids)


def carregar():
    """No Space, o aluno em bf16 no ZeroGPU. Com GGUF=arquivo, o aluno em GGUF na CPU, para testar sem GPU."""
    if os.environ.get("GGUF"):
        m = ModeloGGUF(os.environ["GGUF"], n_threads=int(os.environ.get("THREADS", "2")))
        m.aquecer(m.tok(prompt_sistema(m.tok), add_special_tokens=False)["input_ids"])
        return m
    return ModeloNaGPU(os.environ.get("ADAPTADOR", REPO_LORA))


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
