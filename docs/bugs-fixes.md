# Bugs & Fixes — KDE AI Agent Panel

## 2026-05-30 — NVIDIA Wayland "Error 71 Protocol Error" Crash (Tauri)

### Bug
Tauri app crashes immediately on launch with:
```
Gdk-Message: Error 71 (Protocol error) dispatching to Wayland display.
```
Window opens then closes instantly. Happens on NVIDIA RTX 3070 + driver 595.71.05 + KWin Wayland.

### Root Cause
GTK4 uses DMA-BUF renderer by default on Wayland, which conflicts with NVIDIA's GBM implementation. The `wl_display@1: error 71` is a protocol-level error when GTK4 tries to pass DMA-BUF buffers through KWin.

### Fix Applied
**Key fix: `GSK_RENDERER=ngl`** — forces GTK4 to use OpenGL renderer instead of DMA-BUF.

```bash
# ~/.config/environment.d/gsk.conf (persistent, loaded by systemd user session)
GSK_RENDERER=ngl
```

**Full set of env vars** (`/etc/environment`):
```
GSK_RENDERER=ngl          # KEY FIX — OpenGL renderer for GTK4 on NVIDIA
NVD_BACKEND=direct        # VA-API hardware acceleration
GDK_BACKEND=wayland       # Native Wayland (no XWayland fallback)
```

**Files changed:**
- `/etc/environment` — added GSK_RENDERER, NVD_BACKEND, GDK_BACKEND
- `~/.config/environment.d/gsk.conf` — GSK_RENDERER=ngl (systemd user session)
- `scripts/tauri-wayland.sh` — updated with GSK_RENDERER=ngl as primary fix
- `package.json` — added `tauri:wayland` script
- `install.sh` — added Step 6/6 for automatic NVIDIA Wayland setup

### Verification
```bash
# Check env vars
echo $GSK_RENDERER   # should print "ngl"
echo $NVD_BACKEND    # should print "direct"
echo $GDK_BACKEND    # should print "wayland"

# Launch Tauri with Wayland
./scripts/tauri-wayland.sh
# or
pnpm tauri:wayland
```

### References
- https://forums.opensuse.org/t/gdk-message-error-71-protocol-error-dispatching-to-wayland-display/178886
- https://docs.gtk.org/gtk4/running.html (GSK_RENDERER env var documentation)

### Notes
- `GSK_RENDERER=ngl` is the **critical** fix — without it, Tauri crashes even with other vars set
- `libva-nvidia-driver` 0.0.17-1 already installed
- NVIDIA driver 595.71.05 supports syncobj protocol
- WebKitGTK 2.52.3 has native Wayland support
- `environment.d` config takes effect after logout/login; use `export` for immediate testing

---

## 2026-05-28 — Tool Schema Format Mismatch

### Bug
Agent loop made 50 iterations with 0 tool calls, ended in error:
```
Status: {"status": "error", "iteration": 50, "tool_calls": 0, ...}
```

### Root Cause
`ToolRegistry.get_tool_schemas()` returned tools in Anthropic format:
```json
{"name": "bash_exec", "description": "...", "input_schema": {...}}
```

But OpenAI-compatible providers (llama.cpp, Ollama, OpenRouter) expect:
```json
{"type": "function", "function": {"name": "bash_exec", "description": "...", "parameters": {...}}}
```

llama.cpp error log:
```
Failed to parse tools: Missing tool type: {"name":"bash_exec",...}
```

### Additional Issue
Agent service ran from `~/.local/share/kde-ai-agent/agent/` (separate copy), not from repo. Fix had to be copied there manually.

### Fix Applied

**Files changed:**
- `agent/tools.py` — `get_tool_schemas(fmt="openai")` now supports 3 formats: `openai`, `anthropic`, `internal`. Default is OpenAI.
- `agent/llm_client.py`:
  - `OpenAICompatibleProvider._build_body()` — converts tool schemas to OpenAI format
  - `OllamaProvider._build_body()` — same conversion
  - `OpenAICompatibleProvider._parse_sse_event()` — accumulates tool_calls on `finish_reason == "tool_calls"`
  - `OllamaProvider.stream_message()` — added tool_calls parsing (was missing entirely)
  - `send_message()` in both providers — converts OpenAI-format tool_calls to internal `{id, name, input}`
- `agent/mcp_client.py` — `get_tool_schemas()` returns OpenAI-format
- `agent/context_manager.py` — Added `## Tool Use Policy` section to system prompt

### Verification
```bash
# Before fix: 50 iterations, 0 tool calls, error
# After fix: iteration 3, 2 tool calls, status: thinking
python3 -c "
import dbus, json, time
bus = dbus.SessionBus()
proxy = bus.get_object('org.kde.aiagent', '/org/kde/aiagent')
iface = dbus.Interface(proxy, 'org.kde.aiagent')
print('RunTask:', iface.RunTask('Say hello in one sentence', []))
time.sleep(30)
print('Status:', json.dumps(json.loads(iface.GetStatus()), indent=2))
"
# Result: iteration 3, tool_calls 2, status thinking
```

### TTS Confirmation
Agent responded via voice: **"Hello, how can I help you today?"** — confirmed TTS output works.

### Important Note
Agent service runs from `~/.local/share/kde-ai-agent/agent/`, not from repo. After any agent/ changes:
```bash
cp agent/tools.py ~/.local/share/kde-ai-agent/agent/tools.py
cp agent/llm_client.py ~/.local/share/kde-ai-agent/agent/llm_client.py
cp agent/mcp_client.py ~/.local/share/kde-ai-agent/agent/mcp_client.py
cp agent/context_manager.py ~/.local/share/kde-ai-agent/agent/context_manager.py
cp agent/agent_loop.py ~/.local/share/kde-ai-agent/agent/agent_loop.py
```
Then restart the agent process.

## 2026-05-28 — Tauri Wayland Build Fix & D-Bus Bridge

### Bug 1: `app_handle.runtime()` not found in `AppHandle`
**Error**: `method not found in 'AppHandle'` — Tauri 2 API changed.
**Fix**: Replaced `app_handle.runtime().clone()` + `runtime.spawn()` with `tauri::async_runtime::spawn()` in `dbus_listener.rs`.

### Bug 2: LayerShell crashes on Wayland
**Error**: `Gdk-Message: Error 71 (Protocol error) dispatching to Wayland display` — Tauri's GTK Wayland backend conflicts with separate `wayland-client` connection in `layer_shell.rs`.
**Fix**: Disabled LayerShell setup in `lib.rs`. LayerShell needs gtk4-layer-shell or KWin native panel protocol instead.

### Bug 3: Wrong agent_dir path
**Error**: Tauri looked for `dbus_helper.py` in repo path, but agent service runs from `~/.local/share/kde-ai-agent/agent/`.
**Fix**: Updated `agent_dir` in both `lib.rs` and `commands.rs` to point to `~/.local/share/kde-ai-agent/agent/`.

### Bug 4: Missing dbus_listener.py in service directory
**Error**: `dbus_listener.py not found at ...` — file was never copied to service location.
**Fix**: Copied `dbus_listener.py` and `dbus_helper.py` from repo to `~/.local/share/kde-ai-agent/agent/`.

### Files changed:
- `src-tauri/src/dbus_listener.rs` — `tauri::async_runtime::spawn()` instead of `app_handle.runtime().spawn()`
- `src-tauri/src/lib.rs` — Disabled LayerShell, fixed agent_dir path
- `src-tauri/src/commands.rs` — Fixed agent_dir path
- `~/.local/share/kde-ai-agent/agent/dbus_listener.py` — Deployed from repo
- `~/.local/share/kde-ai-agent/agent/dbus_helper.py` — Deployed from repo

### Verification:
- Tauri app runs via XWayland (`GDK_BACKEND=x11 cargo tauri dev`)
- Window visible: 400×700 at position (2240, 863)
- D-Bus signals received: StatusChanged, TokenStream, ToolCallResult, TaskComplete
- Agent task executed: "What is 2+2?" → 6 iterations, 4 tool calls, status: complete

## 2026-05-28 — llama.cpp TurboQuant Crash (ggml_abort in common_context_seq_rm)

### Bug
llama-server (TheTom/turboquant fork) crashes with `ggml_abort()` in `common_context_seq_rm` → `server_context_impl::update_slots()` when processing requests from the agent.

### Root Cause
The TheTom/llama-cpp-turboquant fork adds `turbo3`/`turbo4` KV cache types (Walsh-Hadamard rotated polar quantization). These turbo cache types are **unstable with MoE models** (Qwen3.6-35B-A3B):
- `--cache-type-k turbo4` causes sequence removal to fail with GGML_ABORT
- `--kv-unified` + `--cont-batching` exacerbate the issue with MoE layer offloading
- Crash happens during slot cleanup between agent iterations

Research references:
- Reddit: "Qwen3.6 does not like TurboQuant" — confirms instability
- GitHub issue #22450: "Qwen3.6-35B-A3B MoE — slot hangs in TG after multi-turn requests"
- The turbo cache types are not yet merged into mainline llama.cpp

### Fix Applied
Use standard KV cache types instead of turbo:
```bash
# BEFORE (crashes):
--cache-type-k turbo4 --cache-type-v turbo2 --kv-unified --cont-batching

# AFTER (stable):
--cache-type-k q8_0 --cache-type-v q4_0
# Removed: --kv-unified, --cont-batching
```

### Working launch command
```bash
/home/neo/ecosystem/thetom.cpp/build/bin/llama-server \
  --model /home/neo/ecosystem/models/Qwen3.6-35B-A3B-wasserstein.IQ3_M.gguf \
  --no-mmproj --port 8085 --jinja --mlock \
  -c 65536 \
  --flash-attn on --reasoning on \
  --n-gpu-layers 36 --n-cpu-moe 32 \
  --cache-type-k q8_0 --cache-type-v q4_0 \
  --batch-size 512 --parallel 1 --ubatch-size 512 \
  --threads 6 --threads-batch 6 \
  --timeout 600 \
  --cache-ram 32768 \
  --temp 0.3 --top-p 0.95 --min-p 0.1 --top-k 20 \
  --no-mmap --metrics
```

### Verification
- Agent task: "What is 2+2? Answer in one sentence." → 3 iterations, 2 tool calls, status: **complete**
- llama-server stable for 1+ hour under agent load
- No ggml_abort crashes

### Trade-offs
- KV cache uses more VRAM (q8_0/q4_0 vs turbo4/turbo2)
- Context reduced from 114688 to 65536 to fit VRAM
- Still fits Qwen3.6-35B with 40 GPU layers + 32 CPU MoE layers on RTX 3070