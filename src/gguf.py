"""Funde o LoRA do aluno no Qwen3-1.7B e gera o GGUF quantizado que roda na CPU (demo e llama.cpp).

uso: python src/gguf.py --adaptador runs/aluno --llama-cpp /mnt/hd/ml/llama.cpp --saida runs/gguf [--quant Q8_0]

O llama.cpp precisa estar compilado com o alvo llama-quantize, no mesmo commit do llama-cpp-python instalado.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

NOME = "qwen3-1.7b-agente-suporte-ptbr"


def fundir(adaptador: str, destino: Path, base: str = "Qwen/Qwen3-1.7B") -> None:
    """LoRA fundido no modelo base, em bf16, na CPU."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    m = AutoModelForCausalLM.from_pretrained(base, dtype=torch.bfloat16)
    PeftModel.from_pretrained(m, adaptador).merge_and_unload().save_pretrained(destino)
    AutoTokenizer.from_pretrained(base).save_pretrained(destino)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adaptador", default="runs/aluno")
    ap.add_argument("--llama-cpp", default="/mnt/hd/ml/llama.cpp")
    ap.add_argument("--saida", default="runs/gguf")
    ap.add_argument("--quant", default="Q4_K_M")
    args = ap.parse_args()

    saida, lcpp = Path(args.saida), Path(args.llama_cpp)
    fundido, bf16 = saida / "fundido", saida / f"{NOME}-bf16.gguf"
    final = saida / f"{NOME}-{args.quant}.gguf"
    if not (fundido / "config.json").exists():
        fundir(args.adaptador, fundido)
    if not bf16.exists():
        subprocess.run([sys.executable, str(lcpp / "convert_hf_to_gguf.py"), str(fundido), "--outtype", "bf16",
                        "--outfile", str(bf16)], check=True, env={**os.environ, "PYTHONPATH": str(lcpp / "gguf-py")})
    subprocess.run([str(lcpp / "build" / "bin" / "llama-quantize"), str(bf16), str(final), args.quant], check=True)
    print(f"{final} | {final.stat().st_size / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
