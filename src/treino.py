"""LoRA do aluno (Qwen3) em conversas de suporte com ferramentas. Roda numa RX 7600 de 8 GB (ROCm).

Adaptado do train_lora.py do review-aspects-ptbr: a perda continua só nas falas do agente, agora em várias por conversa.

uso: python src/treino.py --conversas runs/geracao/treino.jsonl --out runs/aluno
     python src/treino.py --falsas 3000 --passos 20 --batch 1 --accum 1 --out runs/teste-memoria   # teste de memória
"""
import argparse
import json
import math
import os
import random
import time

# Na RX 7600 (gfx1102), a atenção eficiente em memória do ROCm ainda é experimental. Ligada, o pico de VRAM cai de
# 6,4 para 4,6 GB e o passo fica duas vezes mais rápido numa conversa de 3 mil tokens.
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")
os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "expandable_segments:True")

import torch  # noqa: E402
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

from formato_qwen import renderizar


def conversas_falsas(n: int, tokens: int, tok) -> list[list[dict]]:
    """Conversas realistas repetindo uma volta (cliente, chamada, resultado com acentos, resposta) até `tokens`."""
    def volta(k):
        cid = f"t{k}"
        return [
            {"papel": "cliente", "texto": "Oi, meu pedido do Pão & Cia veio sem o pastel de palmito e o caldo de "
                                          "cana chegou quente. Dá para resolver isso?"},
            {"papel": "agente", "texto": "Vou conferir o seu pedido.",
             "chamadas": [{"id": cid, "nome": "detalhar_pedido", "args": {"pedido_id": f"P{10000 + k}"}}]},
            {"papel": "ferramenta", "id": cid, "nome": "detalhar_pedido", "resultado": {
                "pedido_id": f"P{10000 + k}", "restaurante": "Pão & Cia", "status": "entregue",
                "itens": [{"item_id": f"i{j}", "nome": nome, "preco": "R$ 12,90"} for j, nome in
                          enumerate(["Pastel de palmito", "Caldo de cana", "Coxinha", "Pastel de queijo"], 1)],
                "taxa": "R$ 5,99", "total": "R$ 57,59", "feito_em": "07/11 19:10", "previsto_em": "07/11 19:50",
                "entregue_em": "07/11 20:05", "estornado": False}},
            {"papel": "agente", "texto": "Sinto muito pelo problema. Já reembolsei o pastel de palmito, que não veio. "
                                         "O valor volta para a sua forma de pagamento.", "chamadas": []},
        ]

    conversas = []
    for i in range(n):
        ev, k = [{"papel": "contexto", "texto": f"Cliente logado: Ana (C{i}). Agora: 07/11 20:30."}], 0
        while len(renderizar(ev, tok)[0]) < tokens:
            ev += volta(k)
            k += 1
        conversas.append(ev)
    return conversas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conversas", help="JSONL, uma lista de eventos por linha")
    ap.add_argument("--falsas", type=int, default=0, help="gera conversas falsas com pelo menos N tokens")
    ap.add_argument("--n-falsas", type=int, default=16)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="Qwen/Qwen3-1.7B")
    ap.add_argument("--epochs", type=float, default=2)
    ap.add_argument("--batch", type=int, default=2)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--passos", type=int, default=0, help="limite de passos de otimização (0 = sem limite)")
    args = ap.parse_args()

    torch.manual_seed(0)
    random.seed(0)
    dev = "cuda"
    dtype = torch.bfloat16 if torch.version.hip or torch.cuda.get_device_capability()[0] >= 8 else torch.float32

    tok = AutoTokenizer.from_pretrained(args.model)
    if args.falsas:
        conversas = conversas_falsas(args.n_falsas, args.falsas, tok)
    else:
        with open(args.conversas) as f:
            conversas = [json.loads(l) for l in f if l.strip()]
    enc = [renderizar(ev, tok) for ev in conversas]

    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=dtype).to(dev)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05, task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
    model.print_trainable_parameters()
    base = model.get_base_model()

    def batches():
        order = list(range(len(enc)))
        random.shuffle(order)
        for i in range(0, len(order), args.batch):
            chunk = [enc[j] for j in order[i:i + args.batch]]
            n = -(-max(len(x) for x, _ in chunk) // 32) * 32  # poucos formatos distintos: o ROCm escolhe kernel por formato
            ids = torch.full((len(chunk), n), tok.pad_token_id)
            mask = torch.zeros((len(chunk), n), dtype=torch.long)
            labels = torch.full((len(chunk), n), -100)
            for k, (x, r) in enumerate(chunk):
                ids[k, :len(x)] = torch.tensor(x)
                mask[k, :len(x)] = 1
                labels[k, :len(r)] = torch.tensor(r)
            yield ids.to(dev), mask.to(dev), labels.to(dev)

    def loss_fn(ids, mask, labels):
        # Logits só nas posições das falas do agente: o vocabulário de 151k estouraria os 8 GB na conversa inteira.
        h = base.model(input_ids=ids, attention_mask=mask).last_hidden_state[:, :-1]
        y = labels[:, 1:]
        keep = y != -100
        return torch.nn.functional.cross_entropy(base.lm_head(h[keep]).float(), y[keep])

    steps = math.ceil(len(enc) / args.batch * args.epochs / args.accum)
    if args.passos:
        steps = min(steps, args.passos) if not args.falsas else args.passos
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.0)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / 20) * 0.5 * (1 + math.cos(math.pi * min(s, steps) / steps)))

    tokens = sum(len(x) for x, _ in enc) / len(enc)
    print(f"{len(enc)} conversas | {tokens:.0f} tokens por conversa em média | {steps} passos de otimização")
    model.train()
    step, micro, t0 = 0, 0, time.time()
    while step < steps:
        for b in batches():
            (loss_fn(*b) / args.accum).backward()
            micro += 1
            if micro % args.accum:
                continue
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step(); opt.zero_grad()
            step += 1
            if step % 10 == 0 or step == steps:
                print(f"passo {step}/{steps} | {time.time() - t0:.0f}s", flush=True)
            if step >= steps:
                break

    dt = time.time() - t0
    if not args.falsas:
        model.save_pretrained(args.out)
        tok.save_pretrained(args.out)
    print(f"fim | {dt / steps:.1f} s por passo | batch {args.batch} | {tokens:.0f} tokens por conversa | "
          f"pico VRAM {torch.cuda.max_memory_allocated() / 2**30:.2f} GB")


if __name__ == "__main__":
    main()
