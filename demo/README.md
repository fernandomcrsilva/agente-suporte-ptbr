---
title: Atendente de suporte treinado em casa
emoji: 🛵
colorFrom: yellow
colorTo: red
sdk: gradio
sdk_version: 6.31.0
python_version: "3.12"
app_file: demo/app.py
license: mit
models:
  - FMendonca/qwen3-1.7b-agente-suporte-ptbr-gguf
short_description: Qwen3-1.7B treinado em casa atende um delivery fictício
pinned: false
---

# Atendente de suporte treinado em casa

Você faz o papel do cliente da Garfo Ligeiro, um app de delivery fictício, e quem atende é um Qwen3-1.7B com LoRA. Ele foi treinado numa Radeon RX 7600 de 8 GB com conversas de um professor aberto e roda aqui em GGUF, na CPU gratuita. Ao lado da conversa aparecem as ferramentas que ele chamou e o que mudou no sistema de pedidos.

O código, as medições e as limitações estão no [GitHub](https://github.com/fernandomcrsilva/agente-suporte-ptbr).
