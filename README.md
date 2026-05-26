# KDE AI Agent Panel

An AI coding agent embedded in a **KDE Plasma 6** desktop panel. Chat with **Claude**, **Ollama**, **OpenRouter**, or **OpenAI-compatible** models to read, write, search, and test code — all from your desktop sidebar.

![Status](https://img.shields.io/badge/status-beta-blue)
![KDE Plasma](https://img.shields.io/badge/KDE%20Plasma-6-blue)
![Python](https://img.shields.io/badge/Python-3.14-green)
![GCC](https://img.shields.io/badge/GCC-16-orange)
![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Tests](https://img.shields.io/badge/tests-86%20passed-brightgreen)

---

## Features

- **ReAct Agent Loop** — Reason + Act pattern: the agent thinks, calls tools, reads results, and iterates (up to 50 iterations)
- **Streaming Output** — Tokens stream to the QML chat view in real time
- **Multi-Provider** — Anthropic Claude, Ollama, OpenRouter, OpenAI-compatible
- **12 Built-in Tools** — Code execution, file I/O, search, repo mapping, testing, cross-repo intelligence, system monitoring, voice, TTS
- **MCP Integration** — Connect external MCP servers (lean-ctx, engram, codebase-memory, searxng)
- **RAG Engine** — ChromaDB vector search with Ollama embeddings + sentence-transformers fallback
- **Cross-session Memory** — Store and recall facts across sessions with semantic search
- **Cross-repo Intelligence** — Search and trace code across 10+ indexed reference projects
- **Auto Git Commits** — Every file write is auto-committed with a descriptive message
- **D-Bus Integration** — QML UI communicates with Python backend over D-Bus session bus
- **C++ Native Layer** — GCC 16 optimized pybind11 module for fast RAG operations
- **Web UI** — FastAPI + HTMX browser interface for headless/Docker mode
- **OpenObserve Ready** — Stream all agent events to OpenObserve for real-time monitoring

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  KDE Plasma Panel (QML) / Web UI (FastAPI + HTMX)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐              │
│  │ ChatView │ │TaskInput │ │FileTree  │ │ StatusBar │              │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘              │
│       │            │            │              │                    │
│       └────────────┴────────────┴──────────────┘                    │
│                        │ D-Bus / subprocess                         │
├────────────────────────┼────────────────────────────────────────────┤
│                        ▼                                            │
│  Python Agent Backend (systemd user service)                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  AgentLoop (ReAct)                                           │   │
│  │  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────┐  │   │
│  │  │ LLM      │ │ Tool       │ │ MCP      │ │ Context      │  │   │
│  │  │ Client   │ │ Registry   │ │ Client   │ │ Manager      │  │   │
│  │  │ 4 prov.  │ │ 12 tools   │ │ dynamic  │ │ token budget │  │   │
│  │  └──────────┘ └────────────┘ └──────────┘ └──────────────┘  │   │
│  │                        │                                      │   │
│  │  ┌──────────────────────────────────────────────────────┐    │   │
│  │  │  RAG Engine (ChromaDB)                               │    │   │
│  │  │  codebase · memory · docs — Ollama embeddings        │    │   │
│  │  └──────────────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                        │                                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  C++ Native Layer (GCC 16.1.1 · pybind11)                   │   │
│  │  cosine_similarity · normalize · batch_normalize             │   │
│  │  similarity_matrix · count_tokens · chunk_text               │   │
│  │  LTO thin · PGO · march=native · TurboQuant+ (optional)     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Tool Reference (12 tools)

| Tool | Description |
|------|-------------|
| `bash_exec` | Run shell commands (build, test, git, system queries) |
| `file_read` | Read files with line numbers and directory listing |
| `file_write` | Write/create files with auto git commit |
| `search_codebase` | Regex search across all project files (ripgrep) |
| `repo_map` | Generate tree-sitter structural codebase summary |
| `run_tests` | Auto-detect test framework (pytest, cargo, npm, go, ctest) |
| `ask_user` | Pause and ask you a question via the UI |
| `cross_repo_search` | Search across 10+ indexed reference projects (OpenCode, Jarvis, Aider...) |
| `cross_repo_trace` | Trace function calls through a specific reference project |
| `system_monitor` | Real-time CPU, memory, temperature, disk, uptime (from /proc) |
| `voice_input` | Record + transcribe audio via whisper.cpp |
| `tts_output` | Text-to-speech via espeak-ng / speech-dispatcher |

---

## Requirements

### System
- **Arch Linux** (or any system with `pacman`/`yay`)
- **KDE Plasma 6** (for the plasmoid widget)
- **Python 3.10+** (3.14 recommended)
- **GCC 15+** (for C++ native layer; 16.1.1 recommended)
- **ripgrep** (`rg`) — for codebase search
- **git** — for auto-commits

### API Key (choose one)
- **Anthropic API key** → [console.anthropic.com](https://console.anthropic.com/)
- **Ollama** (local, free) → `pacman -S ollama && ollama serve`
- **OpenRouter** → [openrouter.ai/keys](https://openrouter.ai/keys)

---

## Installation

```bash
git clone https://github.com/kde-ai-agent/kde-ai-agent.git
cd kde-ai-agent/linux-arch-kde-plasma-side-panel
chmod +x install.sh
./install.sh
```

The installer:
1. Installs system packages (plasma-framework, kirigami2, qt6-declarative, python-dbus, ripgrep, git)
2. Installs Python dependencies (`pip install -r agent/requirements.txt`)
3. Builds C++ native layer (`cmake -B build && cmake --build build`)
4. Installs the plasmoid (`kpackagetool6 --install`)
5. Creates and starts a systemd user service for the agent backend
6. Creates a default config at `~/.config/kde-ai-agent/config.json`

---

## Configuration

Edit `~/.config/kde-ai-agent/config.json` or use the **QML Config UI** (right-click plasmoid → Configure):

```json
{
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "api_key": "sk-ant-api03-your-key-here",
    "ollama_host": "http://localhost:11434",
    "ollama_model": "llama3.2",
    "max_tokens": 8192,
    "max_input_tokens": 100000,
    "temperature": 0.7,
    "working_dir": "/home/you/projects/my-project",
    "openobserve_endpoint": "",
    "openobserve_stream": "ai-agent-events",
    "mcp_servers": {
        "lean-ctx": {
            "transport": "stdio",
            "command": "lean-ctx",
            "auto_approve": ["ctx_read", "ctx_search"]
        }
    }
}
```

### MCP Server Configuration

Configure external MCP servers in the **ConfigApi.qml** UI or directly in `config.json`:

| Server | Transport | Tools |
|--------|-----------|-------|
| **lean-ctx** | stdio | ctx_read, ctx_search, ctx_graph, ctx_knowledge |
| **engram** | stdio | mem_save, mem_search, mem_context |
| **codebase-memory** | stdio | search_graph, search_code, trace_path |
| **searxng** | stdio/sse | searxng_web_search, web_url_read |

---

## Usage

### Adding to your Panel
1. Right-click your KDE panel → **Add Widgets**
2. Search for **"AI Agent Panel"**
3. Drag it to your desired panel location

### Sending Tasks
1. Type your task in the input field
2. Press **Ctrl+Enter** or click **Send**
3. Watch the agent think, execute tools, and stream results

### Context Files
- Click the **File** button or **Files** in the status bar
- Browse and select files to add context (multi-select with checkboxes)
- Selected files appear as chips above the input

### Keybinds
| Key | Action |
|-----|--------|
| `Ctrl+Enter` | Send task |
| `Esc` | Clear input |

---

## Development

### Project Structure

```
linux-arch-kde-plasma-side-panel/
├── agent/                          # Python backend
│   ├── __init__.py                 # Package exports, version 0.3.0
│   ├── main.py                     # D-Bus service entry point
│   ├── agent_loop.py               # ReAct loop + MCP routing
│   ├── tools.py                    # 12 tool implementations
│   ├── llm_client.py               # 4 provider abstractions
│   ├── context_manager.py          # Token budget management
│   ├── mcp_server.py               # MCP server (stdio + SSE)
│   ├── mcp_client.py               # MCP client (dynamic servers)
│   ├── rag.py                      # RAG engine (ChromaDB)
│   └── requirements.txt
├── src/                            # C++ native layer
│   ├── rag_native.h                # Header: cosine, normalize, chunk
│   ├── embedding.cpp               # Fast embedding operations
│   ├── tokenizer.cpp               # UTF-8 token counting + chunking
│   └── rag_native.cpp              # pybind11 module wrapper
├── cmake/                          # CMake modules
│   ├── CompilerFlags.cmake         # GCC 16 flags (LTO, PGO, march)
│   ├── BuildLlama.cmake.in         # TurboQuant+ fork build
│   └── BuildWhisper.cmake.in       # whisper.cpp build
├── tests/                          # Test suite
│   ├── conftest.py                 # MockToolRegistry + fixtures
│   ├── test_mcp_server.py          # 13 MCP server tests
│   ├── test_mcp_client.py          # 19 MCP client tests
│   ├── test_rag.py                 # 24 RAG engine tests
│   └── test_tools.py               # 24 ToolRegistry tests
├── web/                            # Web UI (headless mode)
│   ├── app.py                      # FastAPI + HTMX server
│   └── templates/                  # Jinja2 templates
├── plasmoid/ai-agent-panel/        # QML plasmoid
│   └── contents/
│       ├── ui/                     # QML components
│       └── config/                 # Config pages + main.xml schema
├── scripts/                        # Build scripts
│   ├── pgo-generate.sh             # PGO profile generation
│   └── pgo-use.sh                  # PGO optimized build
├── .github/workflows/ci.yml        # CI pipeline
├── Dockerfile                      # Docker image
└── install.sh / uninstall.sh
```

### Running the Backend Manually

```bash
# Normal D-Bus mode
cd agent && python3 -m agent.main

# As MCP stdio server (for IDE integration)
python3 -m agent.main --mcp-stdio

# As MCP SSE server on port 8765
python3 -m agent.main --mcp-sse

# Web UI (headless)
python3 -m web.app
# → http://localhost:8080
```

### Building C++ Native Layer

```bash
# Standard build (GCC 16)
cmake -B build
cmake --build build -j$(nproc)

# With TurboQuant+ (llama.cpp fork)
cmake -B build -DBUILD_LLAMA=ON
cmake --build build -j$(nproc)

# PGO optimized build
./scripts/pgo-generate.sh   # Step 1: generate profile
./scripts/pgo-use.sh        # Step 2: use profile
```

### Running Tests

```bash
# All unit tests
python -m pytest tests/ -v

# With ChromaDB integration tests
RAG_INTEGRATION_TESTS=1 python -m pytest tests/ -v

# Coverage report
python -m pytest tests/ --cov=agent --cov-report=term-missing
```

### Testing D-Bus

```bash
systemctl --user status kde-ai-agent
qdbus org.kde.aiagent /org/kde/aiagent org.kde.aiagent.GetStatus
qdbus org.kde.aiagent /org/kde/aiagent org.kde.aiagent.RunTask "Create hello.txt" "[]"
```

---

## Docker

```bash
# Build
docker build -t kde-ai-agent .

# Run (headless MCP SSE mode)
docker run -v ~/.config/kde-ai-agent:/root/.config/kde-ai-agent \
  -p 8765:8765 kde-ai-agent
```

---

## Uninstall

```bash
chmod +x uninstall.sh
./uninstall.sh
```

---

## License

GPL-3.0 — See [LICENSE](LICENSE)

---

## Credits

Patterns and inspiration from:
- **JARVIS** (novik133/jarvis) — KDE Plasma 6 plasmoid structure, system monitoring
- **end4** (dots-hyprland) — AI sidebar streaming pattern
- **Aider** (Aider-AI/aider) — ReAct loop + repo map
- **OpenCode** (opencode-ai/opencode) — MCP client, PubSub, permission system
- **ZooCode / Roo Code** — MCP auto-approval, tool execution interface
- **TurboQuant+** (TheTom/turboquant_plus) — Extreme KV cache compression (ICLR 2026)
