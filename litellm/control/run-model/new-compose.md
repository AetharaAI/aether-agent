networks:
  aether-ai:
    external: true

services:
  qwen35-122b-a10b:
    image: vllm/vllm-openai:latest
    container_name: qwen35-122b-instruct
    runtime: nvidia
    networks:
      - aether-ai
    extra_hosts:
      - "host.docker.internal:host-gateway"
    env_file:
      - .env
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - VLLM_WORKER_MULTIPROC_METHOD=spawn
      - HF_HOME=/models
    volumes:
      - /mnt/aetherpro-extra1/llms/Qwen3.5/cyankiwi/Qwen3.5-122B-A10B-AWQ-4bit:/models
      - ./logs/qwen35-122b:/logs
    command:
      --model /models
      --served-model-name qwen35-122b-instruct
      --host 0.0.0.0
      --port 8001
      --tensor-parallel-size 2
      --gpu-memory-utilization 0.90
      --max-model-len 65536
      --dtype auto
      --kv-cache-dtype fp8
      --disable-log-requests
      --max-num-seqs 6
      --max-num-batched-tokens 8192
      --swap-space 8
      --enable-auto-tool-choice
      --tool-call-parser hermes
      --enable-prefix-caching
      --disable-custom-all-reduce
      --generation-config vllm
      --enable-chunked-prefill
      --reasoning-parser qwen3
      --limit-mm-per-prompt image=5,video=1
    restart: unless-stopped
```

---

## What Changed vs Your Current Config and Why

**`--max-model-len 65536`** — dropped from 262144. The 122B vision model needs more VRAM for the vision encoder. Starting at 64K is safer for a first deploy. You can push it up to 131072 once you confirm it loads clean.

**`--gpu-memory-utilization 0.90`** — dropped from 0.92. Vision encoder adds memory overhead on top of the LLM weights. Small buffer matters here.

**`--max-num-seqs 6`** — dropped from 8. More conservative with a larger active param count.

**`--max-num-batched-tokens 8192`** — halved. Vision tokens are expensive, this prevents OOM on mixed batches.

**`--reasoning-parser qwen3`** — NEW. Required to get the thinking mode working properly with `<think>` tags.

**`--limit-mm-per-prompt image=5,video=1`** — NEW. Required for vision models in vLLM. Caps images per request to prevent VRAM spikes.

---

## Before You Deploy

Update your volume path to wherever you download the model:
```
/mnt/aetherpro-extra1/llms/Qwen3.5/cyankiwi/Qwen3.5-122B-A10B-AWQ-4bit
