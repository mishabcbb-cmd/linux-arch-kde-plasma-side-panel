#!/bin/bash
# A2A LLM Agents — запуск всех 3 агентов
#
# Требует:
#   OPENROUTER_API_KEY_1 — для owl-coder
#   OPENROUTER_API_KEY_2 — для owl-researcher
#   llama.cpp на localhost:8085
#
# Использование:
#   export OPENROUTER_API_KEY_1="sk-or-v1-..."
#   export OPENROUTER_API_KEY_2="sk-or-v1-..."
#   ./start_agents.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
HUB_URL="http://127.0.0.1:9000"
LLAMA_HOST="${LLAMA_HOST:-http://127.0.0.1:8085}"

# Проверить ключи
if [ -z "$OPENROUTER_API_KEY_1" ]; then
    echo "ERROR: OPENROUTER_API_KEY_1 not set"
    exit 1
fi
if [ -z "$OPENROUTER_API_KEY_2" ]; then
    echo "ERROR: OPENROUTER_API_KEY_2 not set"
    exit 1
fi

# Проверить llama.cpp
if ! curl -s "$LLAMA_HOST/v1/models" > /dev/null 2>&1; then
    echo "ERROR: llama.cpp not responding at $LLAMA_HOST"
    exit 1
fi

echo "╔══════════════════════════════════════════╗"
echo "║     A2A LLM Agents — Starting All       ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Hub:   $HUB_URL"
echo "║  llama: $LLAMA_HOST"
echo "╚══════════════════════════════════════════╝"

# Запустить Hub (если ещё не запущен)
if ! curl -s "$HUB_URL/health" > /dev/null 2>&1; then
    echo "Starting A2A Hub..."
    cd "$PROJECT_DIR"
    python run.py &
    HUB_PID=$!
    sleep 2
    echo "  ✓ Hub started (PID: $HUB_PID)"
else
    echo "  ✓ Hub already running"
fi

# Agent 1: OWL Coder (OpenRouter)
echo "Starting owl-coder (OpenRouter/owl-alpha)..."
python "$SCRIPT_DIR/agent_server.py" \
    --name "owl-coder" \
    --provider openrouter \
    --model "openrouter/owl-alpha" \
    --port 8091 \
    --hub-url "$HUB_URL" \
    --capabilities code_analysis code_generation debugging refactoring bash_execution file_operations \
    --api-key "$OPENROUTER_API_KEY_1" \
    > /tmp/owl-coder.log 2>&1 &
CODER_PID=$!
echo "  ✓ owl-coder on :8091 (PID: $CODER_PID)"

# Agent 2: OWL Researcher (OpenRouter)
echo "Starting owl-researcher (OpenRouter/owl-alpha)..."
python "$SCRIPT_DIR/agent_server.py" \
    --name "owl-researcher" \
    --provider openrouter \
    --model "openrouter/owl-alpha" \
    --port 8092 \
    --hub-url "$HUB_URL" \
    --capabilities web_search summarization fact_checking research rag \
    --api-key "$OPENROUTER_API_KEY_2" \
    > /tmp/owl-researcher.log 2>&1 &
RESEARCHER_PID=$!
echo "  ✓ owl-researcher on :8092 (PID: $RESEARCHER_PID)"

# Agent 3: Qwen Reviewer (llama.cpp)
echo "Starting qwen-reviewer (llama.cpp/Qwen3.6-35B)..."
python "$SCRIPT_DIR/agent_server.py" \
    --name "qwen-reviewer" \
    --provider llama.cpp \
    --model "Qwen3.6-35B-A3B-wasserstein.IQ3_M" \
    --port 8093 \
    --hub-url "$HUB_URL" \
    --capabilities code_review security_analysis performance_analysis code_analysis \
    --llama-host "$LLAMA_HOST" \
    > /tmp/qwen-reviewer.log 2>&1 &
REVIEWER_PID=$!
echo "  ✓ qwen-reviewer on :8093 (PID: $REVIEWER_PID)"

# Сохранить PID
echo "$HUB_PID $CODER_PID $RESEARCHER_PID $REVIEWER_PID" > /tmp/a2a-agents.pids

sleep 2

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     All Agents Started                   ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Hub:          http://127.0.0.1:9000     ║"
echo "║  OWL Coder:    http://127.0.0.1:8091     ║"
echo "║  OWL Research: http://127.0.0.1:8092     ║"
echo "║  Qwen Review:  http://127.0.0.1:8093     ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Logs: /tmp/owl-coder.log /tmp/owl-researcher.log /tmp/qwen-reviewer.log"
echo "Stop: ./stop_agents.sh"
