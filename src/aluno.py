"""O aluno (Qwen3 com ou sem LoRA) como agente, rodando na GPU local, no mesmo protocolo do loop de conversa.

uso: python src/aluno.py   # conferência: uma conversa roteirizada com o Qwen3-1.7B sem treino
"""
import os

# As mesmas variáveis do treino: a atenção eficiente do ROCm na RX 7600 (gfx1102).
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")
os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "expandable_segments:True")

from custo import Uso  # noqa: E402
from formato_qwen import PROMPT_ALUNO, interpretar, prompt_geracao  # noqa: E402
from prompts import professor  # noqa: E402

SISTEMA_ALUNO = PROMPT_ALUNO


def sistema_completo() -> str:
    """O prompt inteiro do professor, com a política escrita: a melhor chance para o Qwen sem treino."""
    return professor()


class ModeloQwen:
    def __init__(self, modelo: str = "Qwen/Qwen3-1.7B", adaptador: str | None = None, max_novos: int = 400):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tok = AutoTokenizer.from_pretrained(modelo)
        m = AutoModelForCausalLM.from_pretrained(modelo, dtype=torch.bfloat16)
        if adaptador:
            from peft import PeftModel
            # fundido antes de ir para a GPU: gera mais rápido e funciona no ZeroGPU, que só empresta a GPU na geração
            m = PeftModel.from_pretrained(m, adaptador).merge_and_unload()
        self.m = m.to("cuda").eval()
        self.fim = self.tok.convert_tokens_to_ids("<|im_end|>")
        self.max_novos = max_novos

    def gerar(self, ids: list[int]) -> str:
        import torch
        with torch.no_grad():
            x = torch.tensor([ids], device="cuda")
            out = self.m.generate(x, attention_mask=torch.ones_like(x), max_new_tokens=self.max_novos,
                                  do_sample=False, eos_token_id=self.fim, pad_token_id=self.tok.pad_token_id)
        return self.tok.decode(out[0, len(ids):], skip_special_tokens=False)


class ModeloGGUF:
    """O aluno em GGUF na CPU (llama.cpp), com a mesma interface do ModeloQwen.

    Os ids vêm do prompt_geracao, com o tokenizer do Hugging Face, e a saída é decodificada por ele: o template de chat
    embutido no GGUF nunca é usado, porque o aluno foi treinado no formato do formato_qwen.py.
    """

    def __init__(self, caminho: str, tokenizer: str = "Qwen/Qwen3-1.7B", n_threads: int = 2, n_ctx: int = 8192,
                 max_novos: int = 400):
        from llama_cpp import Llama
        from transformers import AutoTokenizer

        self.tok = AutoTokenizer.from_pretrained(tokenizer)
        self.llm = Llama(model_path=caminho, n_ctx=n_ctx, n_threads=n_threads, n_threads_batch=n_threads,
                         verbose=False)
        self.fins = {self.tok.convert_tokens_to_ids(t) for t in ("<|im_end|>", "<|endoftext|>")}
        self.n_ctx, self.max_novos = n_ctx, max_novos

    def aquecer(self, ids: list[int]) -> None:
        """Lê um prefixo fixo (o prompt de sistema) para a primeira fala não pagar por ele."""
        self.llm.eval(ids)

    def gerar(self, ids: list[int]) -> str:
        if len(ids) >= self.n_ctx:
            raise ValueError(f"conversa maior que o contexto: {len(ids)} tokens de {self.n_ctx}")
        novos = []
        # gulosa (temp 0); o llama.cpp reaproveita o cache do prefixo que se repete entre as falas
        for t in self.llm.generate(ids, temp=0.0, repeat_penalty=1.0):
            if t in self.fins:
                break
            novos.append(t)
            if len(novos) >= min(self.max_novos, self.n_ctx - len(ids)):
                break
        return self.tok.decode(novos, skip_special_tokens=False)


class AgenteQwen:
    def __init__(self, modelo, sistema: str):
        self.modelo, self.sistema = modelo, sistema
        self.eventos: list[dict] = []
        self.uso = Uso("local")
        self.n = 0

    def passo(self, entrada: list[dict]) -> dict:
        self.eventos += entrada
        saida = self.modelo.gerar(prompt_geracao(self.eventos, self.modelo.tok, self.sistema))
        turno = interpretar(saida, f"q{self.n}_")
        self.n += 1
        self.eventos.append({"papel": "agente", **turno})
        return turno


if __name__ == "__main__":
    from cenarios import gerar
    from conversa import rodar

    class Roteiro:
        def __init__(self, falas):
            self.falas = iter(falas)

        def falar(self, texto_agente):
            if texto_agente:
                print("AGENTE:", texto_agente)
            return next(self.falas, None)

    conv = rodar(gerar(0, "atraso"), AgenteQwen(ModeloQwen(), sistema_completo()),
                 Roteiro(["Oi, meu pedido chegou atrasado e eu quero reclamar.", "Tá bom, obrigado."]))
    for e in conv.eventos:
        print(e["papel"], "|", e.get("texto", ""), e.get("chamadas", ""), str(e.get("resultado", ""))[:120])
    print("fim:", conv.motivo_fim, "| estado:", conv.estado)
