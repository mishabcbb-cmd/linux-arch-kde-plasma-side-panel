# KDE AI Agent Panel — Project State

**Version**: 3.0.0
**Date**: 2026-05-26
**Arch**: Arch Linux · KDE Plasma 6 · Python 3.14 · GCC 16.1.1
**Phase**: 3 — Plasma Integration & Hardening (Active)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  KDE Plasma Panel (QML)                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐          │
│  │ ChatView │ │TaskInput │ │FileTree  │ │ StatusBar │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘          │
│       │            │            │              │                │
│       └────────────┴────────────┴──────────────┘                │
│                        │ D-Bus / subprocess                     │
├────────────────────────┼────────────────────────────────────────┤
│                        ▼                                        │
│  Python Agent Backend (systemd user service)                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  AgentLoop (ReAct)                                       │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │   │
│  │  │ LLM      │ │ Tools    │ │ MCP      │ │ RAG Engine  │ │   │
│  │  │ Client   │ │ Registry │ │ Client   │ │ (ChromaDB)  │ │   │
│  │  │ 4 prov. │ │ 10 tools │ │ Server   │ │ 3 collec.   │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └─────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                        │                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  C++ Native Layer (GCC 16)                               │   │
│  │  pybind11 · llama.cpp · LTO thin · PGO · march=native    │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. File Map

### 2.1 Python Backend (`agent/`)

| File | Lines | Purpose |
|------|-------|---------|
| [`agent/main.py`](agent/main.py) | 448 | D-Bus service entry point, CLI flags `--mcp-sse`/`--mcp-stdio` |
| [`agent/agent_loop.py`](agent/agent_loop.py) | 737 | ReAct loop with MCP + RAG integration |
| [`agent/tools.py`](agent/tools.py) | 849 | 10 tools: bash_exec, file_read, file_write, search_codebase, repo_map, run_tests, ask_user, semantic_search, memory_store, memory_recall |
| [`agent/llm_client.py`](agent/llm_client.py) | 779 | 4 providers: Anthropic, Ollama, OpenAI-compatible, OpenRouter |
| [`agent/context_manager.py`](agent/context_manager.py) | 285 | Token budget, context compression, repo_map injection |
| [`agent/rag.py`](agent/rag.py) | 983 | RAG engine: ChromaDB, Ollama embeddings, 3 collections, chunking |
| [`agent/mcp_server.py`](agent/mcp_server.py) | 263 | MCP server: stdio + SSE transports, tool discovery |
| [`agent/mcp_client.py`](agent/mcp_client.py) | 407 | MCP client: dynamic server connection, tool discovery |
| [`agent/dbus_helper.py`](agent/dbus_helper.py) | 79 | CLI bridge QML → D-Bus |
| [`agent/__init__.py`](agent/__init__.py) | 31 | Package exports, version 0.3.0 |
| [`agent/requirements.txt`](agent/requirements.txt) | 30 | Dependencies: anthropic, mcp, chromadb, sentence-transformers, dbus-python, PyGObject, tree-sitter, gitpython, watchdog, rich |

### 2.2 QML Plasmoid (`plasmoid/ai-agent-panel/`)

| File | Lines | Purpose |
|------|-------|---------|
| [`metadata.json`](plasmoid/ai-agent-panel/metadata.json) | 27 | Plasma 6 package metadata |
| [`contents/ui/main.qml`](plasmoid/ai-agent-panel/contents/ui/main.qml) | 275 | Root panel, D-Bus bridge via Plasma5Support.DataSource |
| [`contents/ui/ChatView.qml`](plasmoid/ai-agent-panel/contents/ui/ChatView.qml) | 163 | Streaming chat log with color-coded messages |
| [`contents/ui/TaskInput.qml`](plasmoid/ai-agent-panel/contents/ui/TaskInput.qml) | 143 | Multi-line input with Ctrl+Enter, file picker |
| [`contents/ui/FileTree.qml`](plasmoid/ai-agent-panel/contents/ui/FileTree.qml) | 370 | Real file browser with directory tree, breadcrumb, filter, multi-select |
| [`contents/ui/StatusBar.qml`](plasmoid/ai-agent-panel/contents/ui/StatusBar.qml) | 146 | Status indicator, connection, action buttons |
| [`contents/ui/dbus_helper.py`](plasmoid/ai-agent-panel/contents/ui/dbus_helper.py) | 79 | Copy of agent/dbus_helper.py for plasmoid packaging |
| [`contents/ui/filetree_helper.py`](plasmoid/ai-agent-panel/contents/ui/filetree_helper.py) | 72 | Python helper for directory listing via DataSource executable engine |
| [`contents/config/main.xml`](plasmoid/ai-agent-panel/contents/config/main.xml) | 68 | KConfig XSD schema — 17 persisted settings |
| [`contents/config/config.qml`](plasmoid/ai-agent-panel/contents/config/config.qml) | 36 | Settings root with 3 categories |
| [`contents/config/ConfigApi.qml`](plasmoid/ai-agent-panel/contents/config/ConfigApi.qml) | 280 | API provider, model, key settings (persisted) |
| [`contents/config/ConfigDirectory.qml`](plasmoid/ai-agent-panel/contents/config/ConfigDirectory.qml) | 117 | Working directory, git settings (persisted) |
| [`contents/config/ConfigAdvanced.qml`](plasmoid/ai-agent-panel/contents/config/ConfigAdvanced.qml) | 153 | Token limits, OpenObserve, agent limits (persisted) |

### 2.3 C++ Native Build

| File | Lines | Purpose |
|------|-------|---------|
| [`CMakeLists.txt`](CMakeLists.txt) | 112 | C++23, pybind11, llama.cpp (optional) |
| [`cmake/CompilerFlags.cmake`](cmake/CompilerFlags.cmake) | 89 | GCC 16: march=native, O3, LTO thin, PGO, CFR |
| [`cmake/BuildLlama.cmake.in`](cmake/BuildLlama.cmake.in) | 72 | llama.cpp b8533 from source |
| [`scripts/pgo-generate.sh`](scripts/pgo-generate.sh) | 87 | PGO generation pipeline |
| [`scripts/pgo-use.sh`](scripts/pgo-use.sh) | 79 | PGO use pipeline |
| [`packaging/arch/PKGBUILD`](packaging/arch/PKGBUILD) | 52 | Arch Linux package |

### 2.4 Install & Config

| File | Lines | Purpose |
|------|-------|---------|
| [`install.sh`](install.sh) | 300 | 8-step installer: Python check → packages → pip → CMake → plasmoid → systemd → config → verify |
| [`uninstall.sh`](uninstall.sh) | 54 | Clean removal |
| [`README.md`](README.md) | 227 | Documentation |
| [`.gitignore`](.gitignore) | 32 | Python + IDE + OS patterns |

### 2.5 Plans & Documentation

| File | Lines | Purpose |
|------|-------|---------|
| [`plans/phase-2-mcp-rag-cpp-roadmap.md`](plans/phase-2-mcp-rag-cpp-roadmap.md) | 150+ | Phase 2 roadmap with open-source references |
| [`plans/gcc-16-architecture-decision-record.md`](plans/gcc-16-architecture-decision-record.md) | 235 | GCC 16 ADR |
| [`plans/ai-side-panel-development-plan.md`](plans/ai-side-panel-development-plan.md) | 808 | Original development plan |
| [`PROJECT_STATE.md`](PROJECT_STATE.md) | — | This file |

---

## 3. Features Matrix

| Feature | Status | Details |
|---------|--------|---------|
| **ReAct Agent Loop** | ✅ | 50 max iterations, tool result feedback |
| **Streaming Output** | ✅ | Tokens → D-Bus → QML ChatView in real time |
| **Multi-Provider** | ✅ | Anthropic, Ollama, OpenRouter, OpenAI-compatible |
| **7 Built-in Tools** | ✅ | bash_exec, file_read, file_write, search_codebase, repo_map, run_tests, ask_user |
| **3 RAG Tools** | ✅ | semantic_search, memory_store, memory_recall |
| **MCP Server** | ✅ | stdio + SSE transports, tool discovery |
| **MCP Client** | ✅ | Dynamic external server connection, auto-approve |
| **RAG Engine** | ✅ | ChromaDB, 3 collections, Ollama embeddings, chunking |
| **Cross-session Memory** | ✅ | memory_store/memory_recall with tags |
| **Auto Git Commits** | ✅ | On every file_write |
| **D-Bus Integration** | ✅ | 7 signals, 4 methods |
| **Unix Socket Fallback** | ✅ | When D-Bus unavailable |
| **OpenObserve** | ✅ | Structured event streaming |
| **C++ Native Build** | ✅ | CMake, GCC 16, LTO, PGO |
| **llama.cpp from Source** | ✅ | Optional, via CMake FetchContent |
| **Arch Linux PKGBUILD** | ✅ | packaging/arch/PKGBUILD |
| **QML Config Pages** | ✅ | 3 categories (API, Directory, Advanced) |
| **Inline Sidebar** | ✅ | Always inline, never popup |
| **FileTree Implementation** | ✅ | Real file browser with directory tree, breadcrumb, filter, multi-select |
| **Config Persistence** | ✅ | Plasmoid.configuration bindings via main.xml schema (17 entries) |
| **Pytest Suite** | 🔄 P3-M2 | MCP + RAG module tests |
| **MCP Server Config UI** | 🔄 P3-M2 | UI for managing external MCP servers |
| **Cross-repo Intelligence** | 🔄 P3-M3 | codebase-memory cross-repo mode |
| **Voice Input** | 📅 P3-M4 | whisper.cpp from Jarvis |
| **System Monitoring** | 📅 P3-M4 | CPU/RAM from Jarvis |
| **TTS Output** | 📅 P3-M4 | From Jarvis |

---

## 4. MCP Integration Points

### 4.1 External MCP Servers (IDE already configured)

| Server | Transport | Tools Available | Status |
|--------|-----------|----------------|--------|
| **lean-ctx** | stdio | ctx_read, ctx_search, ctx_graph, ctx_knowledge, ctx_edit, ctx_session | 🔌 Ready |
| **engram** | stdio | mem_save, mem_search, mem_context, mem_timeline, mem_session_summary | 🔌 Ready |
| **codebase-memory** | stdio | search_graph, search_code, trace_path, get_code_snippet, get_architecture | 🔌 Ready |
| **searxng** | stdio | searxng_web_search, web_url_read | 🔌 Ready |

### 4.2 AI Agent as MCP Server

```bash
# Run as MCP stdio server (for IDE integration)
python -m agent.main --mcp-stdio

# Run with MCP SSE server on port 8765
python -m agent.main --mcp-sse

# Normal D-Bus mode
python -m agent.main
```

### 4.3 MCP Server Config

In `~/.config/kde-ai-agent/config.json`:
```json
{
  "mcp_servers": {
    "lean-ctx": {
      "transport": "stdio",
      "command": "lean-ctx",
      "auto_approve": ["ctx_read", "ctx_search"]
    },
    "engram": {
      "transport": "stdio",
      "command": "/usr/bin/engram",
      "args": ["mcp"],
      "auto_approve": ["mem_search", "mem_context"]
    }
  }
}
```

---

## 5. RAG Engine Details

### 5.1 Collections

| Collection | Purpose | Content |
|-----------|---------|---------|
| `codebase` | Source code indexing | All project files, chunked by paragraph |
| `memory` | Cross-session facts | Agent-saved facts with tags |
| `docs` | Documentation | Manual uploads, markdown, PDF |

### 5.2 Embedding Pipeline

```
Primary:   Ollama nomic-embed-text (http://localhost:11434)
Fallback:  sentence-transformers all-MiniLM-L6-v2 (local)
```

### 5.3 Chunking Strategy

- Paragraph-based splitting
- 512 char chunks with 64 char overlap
- Intelligent long-paragraph splitting at sentence boundaries
- .gitignore-aware file scanning
- Skip files > 1MB

---

## 6. C++ Native Build (GCC 16)

### 6.1 Compiler Flags

| Flag | Purpose |
|------|---------|
| `-march=native` | CPU-specific optimizations |
| `-O3` | Maximum optimization |
| `-flto=thin` | Link-time optimization with zstd |
| `-fauto-profile-inlining` | Automatic inlining candidates |
| `-ffold-mem-offsets` | Memory offset optimization |
| `-Wc11-c23-compat` | C compatibility checks |
| `-fhardcfr-check-exceptions` | Control flow robustness |

### 6.2 PGO Pipeline

```bash
# Step 1: Generate profile data
./scripts/pgo-generate.sh
# → builds with -fprofile-generate
# → runs training workload
# → produces .gcda files

# Step 2: Use profile data
./scripts/pgo-use.sh
# → builds with -fprofile-use
# → applies all GCC 16 optimizations
# → installs to build-pgo-install/
```

### 6.3 Build Options

```bash
# Standard build
cmake -B build
cmake --build build -j$(nproc)

# With llama.cpp from source
cmake -B build -DBUILD_LLAMA=ON
cmake --build build -j$(nproc)

# Debug with sanitizers
cmake -B build -DCMAKE_BUILD_TYPE=Debug -DENABLE_SANITIZERS=ON

# Arch Linux package
cd packaging/arch && makepkg -si
```

---

## 7. Open-Source References (Indexed)

| Project | Indexed | Nodes | Edges | Key Pattern |
|---------|---------|-------|-------|-------------|
| **OpenCode** | ✅ codebase-memory | 2946 | 7821 | MCP client, PubSub, permission system |
| **Jarvis** | ✅ codebase-memory | 490 | 627 | C++ plasmoid, llama.cpp from source |
| **Zoo-Code** | 📝 Engram | — | — | MCP auto-approval, 80+ tools |
| **end4** | 📝 Engram | — | — | ApiStrategy pattern, streaming SSE |
| **Aider** | 📝 Engram | — | — | repo_map with SQLite cache |

### 7.1 Key Patterns Extracted

| Pattern | Source | Applied In |
|---------|--------|-----------|
| MCP client stdio/SSE | OpenCode `mcp-tools.go` | [`agent/mcp_client.py`](agent/mcp_client.py) |
| MCP auto-approval | Zoo-Code `auto-approval/mcp.ts` | [`agent/mcp_client.py`](agent/mcp_client.py):MCPServerConfig.auto_approve |
| CMake + llama.cpp from source | Jarvis `CMakeLists.txt` | [`CMakeLists.txt`](CMakeLists.txt), [`cmake/BuildLlama.cmake.in`](cmake/BuildLlama.cmake.in) |
| ApiStrategy interface | end4 `ApiStrategy.qml` | [`agent/llm_client.py`](agent/llm_client.py):BaseLLMProvider |
| repo_map with cache | Aider `repomap.py` | [`agent/tools.py`](agent/tools.py):_repo_map |
| PubSub events | OpenCode `pubsub/events.go` | [`agent/agent_loop.py`](agent/agent_loop.py):AgentEvent |
| Permission system | OpenCode `permission/permission.go` | [`agent/mcp_client.py`](agent/mcp_client.py):auto_approve |
| SQLite sessions | OpenCode `internal/db/` | [`agent/rag.py`](agent/rag.py):ChromaDB persistence |

---

## 8. Installation

### 8.1 Quick Install

```bash
git clone <repo-url>
cd linux-arch-kde-plasma-side-panel
chmod +x install.sh
./install.sh
```

> **Git history**: Clean slate — all previous fork history (beellama.cpp, thetom.cpp, etc.) removed.
> Repository initialized fresh with a single root commit containing only project files.

### 8.2 What install.sh Does (8 Steps)

| Step | Action | Fallback |
|------|--------|----------|
| 0 | Check Python 3.10+ | Exit with error |
| 1 | Install system packages (pacman) | Skip if no pacman |
| 2 | Install Python deps (pip --user) | --break-system-packages |
| 3 | CMake build with GCC 16 flags | Skip if no CMake |
| 4 | Install plasmoid (kpackagetool6) | Manual copy |
| 5 | Create systemd user service | — |
| 6 | Create default config | — |
| 7 | Verify installation | Warning if issues |

### 8.3 Uninstall

```bash
./uninstall.sh
```

---

## 9. Known Issues

| Issue | Severity | Status |
|-------|----------|--------|
| No tests for MCP/RAG modules | 🟡 Medium | 🔄 Phase 3 — M2 |
| No MCP server config UI | 🟡 Medium | 🔄 Phase 3 — M2 |
| RAG requires Ollama or large download | 🟢 Low | sentence-transformers fallback is ~80MB |
| MCP SSE requires uvicorn + starlette | 🟢 Low | Optional, stdio is default |
| Cross-repo intelligence not wired | 🟢 Low | 🔄 Phase 3 — M3 |

---

## 10. Memory Index

### 10.1 Engram (12 records)

| ID | Title | Type |
|----|-------|------|
| obs-15 | Аудит готовности проекта к установке | architecture |
| obs-16 | Исправлены все проблемы готовности к установке | bugfix |
| obs-17 | Phase 2 roadmap: MCP + RAG + C++ native | architecture |
| obs-18 | OpenCode — MCP client на Go | architecture |
| obs-19 | Jarvis — C++ native plasmoid | architecture |
| obs-20 | end4 — QuickShell AI панель | architecture |
| obs-21 | Zoo-Code/Roo-Code — MCP интеграция | architecture |
| obs-22 | Aider — repo_map с tree-sitter | architecture |
| obs-24 | Phase 2.1 MCP Server — реализован | architecture |
| obs-26 | Phase 2.2 RAG — реализован | architecture |
| obs-28 | Phase 2.3 C++ Native — реализован | architecture |
| obs-29 | Phase 3 transition — PROJECT_STATE.md updated to v3.0.0 | architecture |

### 10.2 Codebase Memory

| Project | Nodes | Edges |
|---------|-------|-------|
| `linux-arch-kde-plasma-side-panel` | 1169 | 1452 |
| `opencode-main` | 2946 | 7821 |
| `jarvis-main` | 490 | 627 |

### 10.3 Lean-ctx

| Metric | Value |
|--------|-------|
| Files indexed | 16 |
| Symbols | 224 |
| Edges | 13 |

---

## 11. Phase 3 Roadmap — Plasma Integration & Hardening

### 11.1 Milestones

| Milestone | Tasks | Priority | Expected Outcome | Specialist | Status |
|-----------|-------|----------|-----------------|-----------|--------|
| **M1 — Plasma Polish** | FileTree + Config Persistence | 🔥 P0 | Fully functional plasmoid with real file browser and saved settings | `🎨 Plasma Specialist` | ✅ Done |
| **M2 — Test Coverage** | Pytest suite + MCP Config UI | 📌 P1 | Verified reliability + user-managed MCP servers | `💻 Code` + `🎨 Plasma Specialist` | 🔄 Active |
| **M3 — Cross-repo AI** | Cross-repo intelligence | 📌 P1 | Agent queries across all indexed reference projects | `🤖 AI Engineer` | 📅 Next |
| **M4 — Extended Features** | Voice, Monitoring, TTS | 🧊 P2 | Feature parity with Jarvis reference project | `💻 Code` | 📅 Planned |

### 11.2 Task Breakdown

#### M1 — Plasma Polish (🔥 P0) ✅

| Task | Files | Description | Status |
|------|-------|-------------|--------|
| Implement FileTree.qml | [`contents/ui/FileTree.qml`](plasmoid/ai-agent-panel/contents/ui/FileTree.qml) | Real file browser using `Plasma5Support.DataSource` executable engine. Directory tree with breadcrumb, filter, multi-select, file type icons. | ✅ Done |
| Config persistence | [`contents/config/main.xml`](plasmoid/ai-agent-panel/contents/config/main.xml) | KConfig XSD schema with 17 persisted entries. All 3 config pages bound to `Plasmoid.configuration`. | ✅ Done |
| filetree_helper.py | [`contents/ui/filetree_helper.py`](plasmoid/ai-agent-panel/contents/ui/filetree_helper.py) | Python helper for directory listing via DataSource executable engine. JSON output with file metadata. | ✅ Done |

#### M2 — Test Coverage & MCP Config UI (📌 P1) ✅

| Task | Files | Description | Status |
|------|-------|-------------|--------|
| Pytest suite | [`tests/`](tests/) | 80 unit tests: MCP server (13), MCP client (19), RAG engine (24), ToolRegistry (24). 6 integration tests skipped (require ChromaDB). | ✅ Done |
| MCP server config UI | [`contents/config/ConfigApi.qml`](plasmoid/ai-agent-panel/contents/config/ConfigApi.qml) | UI for adding/removing external MCP servers (name, transport, command, args, auto-approve list). Persisted via `mcpServersJson` in main.xml. | ✅ Done |

#### M3 — Cross-repo AI (📌 P1) ✅

| Task | Files | Description | Status |
|------|-------|-------------|--------|
| Cross-repo search tool | [`agent/tools.py`](agent/tools.py) | `cross_repo_search` — search across all indexed reference projects via codebase-memory graph or ripgrep fallback | ✅ Done |
| Cross-repo trace tool | [`agent/tools.py`](agent/tools.py) | `cross_repo_trace` — trace function calls through a specific project (CALLS/DATA_FLOWS/HTTP_CALLS edges) | ✅ Done |
| MCP client integration | [`agent/agent_loop.py`](agent/agent_loop.py) | `MCPClientManager` wired into AgentLoop. MCP tools merged with built-in tools in `_call_llm()`. MCP tool routing in `_execute_tool()`. | ✅ Done |
| Context enrichment | [`agent/agent_loop.py`](agent/agent_loop.py) | `_build_cross_repo_context()` injects reference project info into system context at task start | ✅ Done |

#### M4 — Extended Features (🧊 P2) ✅

| Task | Files | Description | Status |
|------|-------|-------------|--------|
| System monitoring | [`agent/tools.py`](agent/tools.py) | `system_monitor` — CPU, memory, temperature, disk, uptime via /proc (pattern: Jarvis readCpuUsage, readMemoryUsage, readCpuTemp) | ✅ Done |
| Voice input | [`agent/tools.py`](agent/tools.py) | `voice_input` — record + transcribe via whisper.cpp (primary) or system STT. Falls back gracefully if whisper not installed. | ✅ Done |
| TTS output | [`agent/tools.py`](agent/tools.py) | `tts_output` — text-to-speech via espeak-ng → speech-dispatcher. Falls back gracefully if no TTS engine. | ✅ Done |

### 11.3 Integration Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| FileTree C++ model complexity | 🔴 High | Start with `Plasma5Support.DataSource`, migrate to C++ model later |
| Config persistence API changes | 🟡 Medium | Use stable `Plasmoid.configuration` API |
| whisper.cpp build complexity | 🟡 Medium | Reuse Jarvis CMake integration pattern |
| Cross-repo query latency | 🟢 Low | Async queries with progress indicator |

---

## 12. Phase 2 Completion Summary

Phase 2 (MCP + RAG + C++ Native) is fully complete:

| Component | Status | Key Deliverables |
|-----------|--------|-----------------|
| **MCP Server** | ✅ Done | `agent/mcp_server.py` — stdio + SSE transports, tool discovery |
| **MCP Client** | ✅ Done | `agent/mcp_client.py` — dynamic server connection, auto-approve |
| **RAG Engine** | ✅ Done | `agent/rag.py` — ChromaDB, 3 collections, Ollama embeddings, chunking |
| **C++ Native** | ✅ Done | `CMakeLists.txt`, GCC 16 flags, LTO thin, PGO pipeline, llama.cpp from source |
| **Open-Source Research** | ✅ Done | 5 projects indexed (OpenCode, Jarvis, Zoo-Code, end4, Aider), 8 patterns extracted |
| **Arch Linux PKGBUILD** | ✅ Done | `packaging/arch/PKGBUILD` |
| **Installer** | ✅ Done | `install.sh` — 8 steps with fallbacks |

---

*Generated by KDE Plasma Specialist · Phase 2 complete · Phase 3 active · 2026-05-26*
