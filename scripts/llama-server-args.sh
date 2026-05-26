#!/bin/bash
# llama.cpp server launch parameters for Qwen3.6-35B-A3B
# GPU: NVIDIA RTX 3070, Wayland, KDE Plasma 6
# Port: 8085 (used by KDE AI Agent)

/home/neo/ecosystem/thetom.cpp/build/bin/llama-server \
    --model /home/neo/ecosystem/models/Qwen3.6-35B-A3B-IQ3_M.gguf \
    --port 8085 \
    --jinja \
    --mlock \
    -c 368640 \
    --rope-scale 1.40625 \
    --rope-scaling yarn \
    --yarn-orig-ctx 262144 \
    --reasoning off \
    --n-gpu-layers 99 \
    --n-cpu-moe 35 \
    --cache-type-k turbo4 \
    --cache-type-v turbo2 \
    --flash-attn on \
    --batch-size 512 \
    --parallel 1 \
    --ubatch-size 512 \
    --threads 6 \
    --threads-batch 12 \
    --cont-batching \
    --timeout 300 \
    --kv-unified \
    --cache-idle-slots \
    --cache-ram 49152 \
    --sleep-idle-seconds 300 \
    --temp 0.3 \
    --top-p 0.95 \
    --min-p 0.1 \
    --top-k 20 \
    --no-mmap \
    --metrics
