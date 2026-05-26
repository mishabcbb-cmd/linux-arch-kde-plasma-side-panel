# KDE AI Agent Panel — Project State

**Version**: 2.0.0
**Date**: 2026-05-26
**Arch**: Arch Linux · KDE Plasma 6 · Python 3.14 · GCC 16.1.1
**Phase**: 3 — Plasma Integration & Hardening

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
| [`contents/ui/main.qml`](plasmoid/ai-agent-panel/contents/ui/main.qml) | 258 | Root panel, D-Bus bridge via Plasma5Support.DataSource |
| [`contents/ui/ChatView.qml`](plasmoid/ai-agent-panel/contents/ui/ChatView.qml) | 163 | Streaming chat log with color-coded messages |
| [`contents/ui/TaskInput.qml`](plasmoid/ai-agent-panel/contents/ui/TaskInput.qml) | 107 | Multi-line input with Ctrl+Enter, file picker |
| [`contents/ui/FileTree.qml`](plasmoid/ai-agent-panel/contents/ui/FileTree.qml) | 124 | File context picker (placeholder — needs implementation) |
| [`contents/ui/StatusBar.qml`](plasmoid/ai-agent-panel/contents/ui/StatusBar.qml) | 146 | Status indicator, connection, action buttons |
| [`contents/ui/dbus_helper.py`](plasmoid/ai-agent-panel/contents/ui/dbus_helper.py) | 79 | Copy of agent/dbus_helper.py for plasmoid packaging |
| [`contents/config/config.qml`](plasmoid/ai-agent-panel/contents/config/config.qml) | 36 | Settings root with 3 categories |
| [`contents/config/ConfigApi.qml`](plasmoid/ai-agent-panel/contents/config/ConfigApi.qml) | 240 | API provider, model, key settings |
| [`contents/config/ConfigDirectory.qml`](plasmoid/ai-agent-panel/contents/config/ConfigDirectory.qml) | 117 | Working directory, git settings |
| [`contents/config/ConfigAdvanced.qml`](plasmoid/ai-agent-panel/contents/config/ConfigAdvanced.qml) | 153 | Token limits, OpenObserve, agent limits |

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
| **File Context** | ⚠️ | FileTree.qml is placeholder |
| **Config Persistence** | ⚠️ | Config pages need save logic |
| **FileTree Implementation** | 🔄 P3 | Real file browser with C++ model or Plasma5Support.DataSource |
| **Config Persistence** | 🔄 P3 | Plasmoid.configuration bindings |
| **Pytest Suite** | 🔄 P3 | MCP + RAG module tests |
| **MCP Server Config UI** | 🔄 P3 | UI for managing external MCP servers |
| **Cross-repo Intelligence** | 🔄 P3 | codebase-memory cross-repo mode |
| **Voice Input** | 📅 P3 | whisper.cpp from Jarvis |
| **System Monitoring** | 📅 P3 | CPU/RAM from Jarvis |
| **TTS Output** | 📅 P3 | From Jarvis |

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
| MCP client stdio/SSE | OpenCode `mcp-tools.go` | `agent/mcp_client.py` |
| MCP auto-approval | Zoo-Code `auto-approval/mcp.ts` | `agent/mcp_client.py:MCPServerConfig.auto_approve` |
| CMake + llama.cpp from source | Jarvis `CMakeLists.txt` | `CMakeLists.txt`, `cmake/BuildLlama.cmake.in` |
| ApiStrategy interface | end4 `ApiStrategy.qml` | `agent/llm_client.py:BaseLLMProvider` |
| repo_map with cache | Aider `repomap.py` | `agent/tools.py:_repo_map` |
| PubSub events | OpenCode `pubsub/events.go` | `agent/agent_loop.py:AgentEvent` |
| Permission system | OpenCode `permission/permission.go` | `agent/mcp_client.py:auto_approve` |
| SQLite sessions | OpenCode `internal/db/` | `agent/rag.py:ChromaDB persistence` |

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
| FileTree.qml is placeholder | 🟡 Medium | 🔄 Phase 3 — P0 |
| Config pages don't persist settings | 🟡 Medium | 🔄 Phase 3 — P0 |
| No tests for MCP/RAG modules | 🟡 Medium | 🔄 Phase 3 — P1 |
| No MCP server config UI | 🟡 Medium | 🔄 Phase 3 — P1 |
| RAG requires Ollama or large download | 🟢 Low | sentence-transformers fallback is ~80MB |
| MCP SSE requires uvicorn + starlette | 🟢 Low | Optional, stdio is default |
| Cross-repo intelligence not wired | 🟢 Low | 🔄 Phase 3 — P1 |

---

## 10. Memory Index

### 10.1 Engram (11 records)

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

| Priority | Task | Specialist | Dependencies |
|----------|------|-----------|-------------|
| 🔥 P0 | Implement FileTree.qml with real file browser | `🎨 Plasma Specialist` | — |
| 🔥 P0 | Add config persistence (Plasmoid.configuration) | `🎨 Plasma Specialist` | — |
| 📌 P1 | Write pytest suite for MCP + RAG modules | `💻 Code` | — |
| 📌 P1 | Add MCP server config UI in ConfigApi.qml | `🎨 Plasma Specialist` | — |
| 📌 P1 | Cross-repo intelligence (codebase-memory mode) | `🤖 AI Engineer` | Pytest suite |
| 🧊 P2 | Voice input (whisper.cpp from Jarvis) | `💻 Code` | C++ native layer |
| 🧊 P2 | System monitoring (CPU/RAM from Jarvis) | `💻 Code` | C++ native layer |
| 🧊 P2 | TTS output (from Jarvis) | `💻 Code` | C++ native layer |

### 11.1 Phase 3 Deliverables

| Milestone | Tasks | Expected Outcome |
|-----------|-------|-----------------|
| **M1 — Plasma Polish** | FileTree + Config Persistence | Fully functional plasmoid with real file browser and saved settings |
| **M2 — Test Coverage** | Pytest suite + MCP Config UI | Verified reliability + user-managed MCP servers |
| **M3 — Cross-repo AI** | Cross-repo intelligence | Agent queries across all indexed reference projects |
| **M4 — Extended Features** | Voice, Monitoring, TTS | Feature parity with Jarvis reference project |

### 11.2 Integration Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| FileTree C++ model complexity | 🔴 High | Start with Plasma5Support.DataSource, migrate to C++ model later |
| Config persistence API changes | 🟡 Medium | Use stable Plasmoid.configuration API |
| whisper.cpp build complexity | 🟡 Medium | Reuse Jarvis CMake integration pattern |
| Cross-repo query latency | 🟢 Low | Async queries with progress indicator |

---

*Generated by Merge Resolver Agent · Phase 2 complete · Phase 3 initiated · 2026-05-26*
