# Compressed Prompt — KDE AI Agent Panel

## Project
KDE Plasma 6 side panel with AI agent (ReAct loop, multi-provider LLM, TTS, D-Bus).

**Repo**: `/home/neo/ecosystem/linux-arch-kde-plasma-side-panel`
**Service code**: `~/.local/share/kde-ai-agent/agent/` (separate copy!)

## Architecture
```
QML Plasmoid → D-Bus → Python Agent (systemd)
                          ├── AgentLoop (ReAct, 50 max iter)
                          ├── ToolRegistry (12 tools)
                          ├── LLM Client (5 providers)
                          │   ├── llama.cpp (Qwen3.6-35B, port 8085)
                          │   ├── Anthropic, Ollama, OpenRouter, LlamaCpp
                          ├── MCP Client (external servers)
                          └── ContextManager (token budget)
```

## Critical Fix (2026-05-28)
**Bug**: 50 iterations, 0 tool calls → error.
**Cause**: Tool schema format mismatch — Anthropic format sent to OpenAI-compatible llama.cpp.
**Fix**: `get_tool_schemas(fmt="openai")` now returns `{type:"function", function:{...}}` by default.
**Files**: `agent/tools.py`, `agent/llm_client.py`, `agent/mcp_client.py`, `agent/context_manager.py`

## ⚠️ IMPORTANT
Agent service runs from `~/.local/share/kde-ai-agent/agent/`, NOT from repo.
After ANY changes to `agent/` files:
```bash
cp agent/tools.py agent/llm_client.py agent/mcp_client.py agent/context_manager.py agent/agent_loop.py ~/.local/share/kde-ai-agent/agent/
```
Then restart: `kill <pid>` or `systemctl --user restart kde-ai-agent`

## Config
`~/.config/kde-ai-agent/config.json`:
```json
{"provider":"llama.cpp","llama_host":"http://localhost:8085","llama_model":"Qwen3.6-35B-A3B-IQ3_M.gguf","max_tokens":8192,"max_input_tokens":100000,"temperature":0.7}
```

## Test Agent
```bash
python3 -c "
import dbus,json,time
bus=dbus.SessionBus()
p=bus.get_object('org.kde.aiagent','/org/kde/aiagent')
i=dbus.Interface(p,'org.kde.aiagent')
print(i.RunTask('test task',[]))
time.sleep(20)
print(json.dumps(json.loads(i.GetStatus()),indent=2))
"
```

## Key Files
| File | Purpose |
|------|---------|
| `agent/main.py` | D-Bus service entry |
| `agent/agent_loop.py` | ReAct loop |
| `agent/tools.py` | 12 tools + schemas |
| `agent/llm_client.py` | 5 LLM providers |
| `agent/context_manager.py` | Token budget |
| `agent/mcp_client.py` | MCP client |
| `plasmoid/ai-agent-panel/contents/ui/SidePanelWindow.qml` | QML UI |

## llama.cpp Config (CRITICAL)
TheTom/turboquant fork with Qwen3.6-35B MoE. Must use STABLE cache types.

**⚠️ DO NOT use** `--cache-type-k turbo4`, `--cache-type-v turbo2`, `--kv-unified`, `--cont-batching` — causes `ggml_abort` crash with MoE models.

**Working launch command:**
```bash
nohup /home/neo/ecosystem/thetom.cpp/build/bin/llama-server \
  --model /home/neo/ecosystem/models/Qwen3.6-35B-A3B-wasserstein.IQ3_M.gguf \
  --no-mmproj --port 8085 --jinja --mlock \
  -c 65536 \
  --flash-attn on --reasoning on \
  --n-gpu-layers 40 --n-cpu-moe 32 \
  --cache-type-k q8_0 --cache-type-v q4_0 \
  --batch-size 512 --parallel 1 --ubatch-size 512 \
  --threads 6 --threads-batch 6 \
  --timeout 600 --cache-ram 32768 \
  --temp 0.3 --top-p 0.95 --min-p 0.1 --top-k 20 \
  --no-mmap --metrics \
  > /tmp/llama-server.log 2>&1 &
```

**Verify:** `curl -s http://localhost:8085/health` → `{"status":"ok"}`

## Status
✅ v4.1.3 — llama.cpp crash fixed (turbo cache → q8_0/q4_0). Agent completes tasks (3 iter, 2 tool calls). Tauri compiles clean (0 warnings). D-Bus bridge working.
