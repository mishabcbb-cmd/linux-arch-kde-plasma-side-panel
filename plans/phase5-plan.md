# Phase 5 — Multi-Agent Architecture & Advanced RAG

**Version**: 1.0.0
**Date**: 2026-05-28
**Author**: 🏗️ Architect + OWL
**Context**: Arch Linux · KDE Plasma 6 · Python 3.14 · GCC 16.1.1 · NVIDIA Wayland · llama.cpp Qwen3.6-35B
**Research**: Kilo Code source analysis, A2A Hub current state, RAG/AgentLoop codebase audit

---

## 1. Executive Summary

Phase 5 превращает проект из одноагентной системы в **полноценную мульти-агентную платформу** с продвинутым RAG, системой плагинов и усиленной безопасностью MCP.

**Ключевые направления:**

| Направление | Impact | Сложность | Приоритет | Статус |
|------------|--------|-----------|-----------|--------|
| Agentic RAG | 🔥 High | Medium | P0 | 📅 Planned |
| Hybrid Search + Re-ranking | 🔥 High | Medium | P0 | 📅 Planned |
| MCP Security Hardening | 🔥 High | Low | P0 | 📅 Planned |
| Multi-Agent Architecture v2 | 📌 Medium | High | P1 | 📅 Planned (A2A Hub v1 exists) |
| Plugin System | 📌 Medium | High | P1 | 📅 Planned |
| Reflexion Pattern | 📌 Medium | Medium | P1 | 📅 Planned |
| GPU Acceleration | 🧊 Medium | High | P2 | 📅 Planned |

---

## 2. Current State Analysis

### 2.1 What Exists (Phase 4 Complete)

```
✅ A2A Hub v1 — HTTP API, 3 agents, conversation log, D-Bus integration
✅ ReAct Agent Loop — 50 max iterations, 12 tools, 5 LLM providers
✅ RAG Engine — ChromaDB, 3 collections, naive vector search
✅ MCP Server + Client — stdio + SSE, 7 MCP tools
✅ QML Side Panel — ChatView, TaskInput, FileTree, StatusBar
✅ Tauri 2 + React — Rust backend, React frontend, D-Bus bridge
✅ C++ Native Layer — GCC 16, LTO thin, PGO
✅ 86 unit tests — all passing
```

### 2.2 What's Missing (Gaps)

```
❌ RAG: no BM25, no re-ranking, no iterative retrieval (naive RAG)
❌ Agent: no Reflexion, no self-correction
❌ Multi-Agent: A2A Hub exists but agents are independent (no orchestration)
❌ Tools: hardcoded in ToolRegistry, no plugin system
❌ MCP: no rate limiting, no input validation, no sandboxing
❌ Tauri: empty window on Wayland (NVIDIA+WebKitGTK issue)
```

### 2.3 Kilo Code Research Findings

From `/home/neo/ecosystem/source-codes/kilocode-main/` source analysis:

| Pattern | Kilo Code Implementation | Applicability |
|---------|-------------------------|---------------|
| **Subagent Delegation** | `task.ts` — `subagent_type` param creates specialized child agents | Direct match for A2A Hub |
| **Worktree Isolation** | `WorktreeManager` — each agent gets own git worktree + branch | Useful for parallel agents |
| **Multi-Model Comparison** | `multi-version.ts` — same prompt, different models, compare results | A2A Hub enhancement |
| **Permission System** | `permission/evaluate.ts` — tool-level permissions | MCP Security Hardening |
| **Compaction** | `session/compaction.ts` — context compression | AgentLoop improvement |
| **Agent Manager UI** | `AgentManagerProvider.tsx` — multi-agent orchestration panel | QML/React UI enhancement |
| **Effect-TS** | All async via Effect — clean error handling | Architecture inspiration |

---

## 3. Architecture Vision

### 3.1 Target Architecture (Phase 5)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        KDE Plasma 6 + Tauri 2                                │
│                                                                              │
│  ┌─────────────────────────┐    ┌──────────────────────────────────────┐     │
│  │  QML SidePanelWindow    │    │  Tauri WebView (React + TS)          │     │
│  │  ┌──────────────────┐   │    │  ┌────────────────────────────────┐  │     │
│  │  │ AgentManager UI  │   │    │  │  Agent Manager Panel           │  │     │
│  │  │ (multi-agent)    │   │    │  │  (inspired by Kilo Code)       │  │     │
│  │  └────────┬─────────┘   │    │  └──────────────┬─────────────────┘  │     │
│  └───────────┼─────────────┘    └─────────────────┼────────────────────┘     │
│              │ D-Bus                                │ Tauri IPC               │
├──────────────┼──────────────────────────────────────┼─────────────────────────┤
│              ▼                                      ▼                         │
│  ┌───────────────────────────────────────────────────────────────────────┐    │
│  │                    A2A Hub v2 (Python)                                │    │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │    │
│  │  │  Orchestrator Agent (Planner + Coordinator + Aggregator)        │  │    │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │  │    │
│  │  │  │ Code     │ │ Search   │ │ Analysis │ │ Test     │          │  │    │
│  │  │  │ Agent    │ │ Agent    │ │ Agent    │ │ Agent    │          │  │    │
│  │  │  │(read/    │ │(codebase │ │(system   │ │(pytest   │          │  │    │
│  │  │  │ write)   │ │ web RAG) │ │ monitor) │ │ cargo)   │          │  │    │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │  │    │
│  │  └─────────────────────────────────────────────────────────────────┘  │    │
│  │  ┌────────────────────┐  ┌────────────────────┐                      │    │
│  │  │  Agentic RAG       │  │  Plugin Manager    │                      │    │
│  │  │  (Hybrid + Rerank) │  │  (Dynamic Load)    │                      │    │
│  │  └────────────────────┘  └────────────────────┘                      │    │
│  │  ┌────────────────────┐  ┌────────────────────┐                      │    │
│  │  │  MCP Security      │  │  Reflexion Memory  │                      │    │
│  │  │  (Rate Limit +     │  │  (Self-Correction) │                      │    │
│  │  │   Validation)      │  │                    │                      │    │
│  │  └────────────────────┘  └────────────────────┘                      │    │
│  └───────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐    │
│  │  C++ Native Layer (GPU-Accelerated)                                   │    │
│  │  CUDA batch_normalize · CUDA similarity_matrix · cuBLAS              │    │
│  └───────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Agent Communication Protocol (Inspired by Kilo Code's task.ts)

```
┌─────────────────────────────────────────────────────────────┐
│  Orchestrator → Subagent Delegation                         │
│                                                             │
│  1. User sends task to Orchestrator                         │
│  2. Orchestrator decomposes into DAG of subtasks            │
│  3. For each subtask:                                       │
│     a. Select agent by capability (router)                  │
│     b. Delegate with context + subtask description          │
│     c. Agent executes (with Reflexion if needed)            │
│     d. Return result + reflection notes                     │
│  4. Orchestrator aggregates results                         │
│  5. Return final answer to user                             │
│                                                             │
│  Parallel execution for independent subtasks                │
│  Sequential execution for dependent subtasks                │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Detailed Milestones

### M1: Quick Wins (P0 — Week 1)

**Цель**: Быстрые улучшения безопасности и качества

| # | Task | Files | Description |
|---|------|-------|-------------|
| 1.1 | MCP Rate Limiting | `a2a_hub/mcp_server/server.py` | Per-agent/per-method quotas, token bucket |
| 1.2 | MCP Input Validation | `a2a_hub/mcp_server/server.py` | JSON Schema validation for all tool inputs |
| 1.3 | Semantic Chunking | `agent/rag.py` | Replace fixed-size with semantic boundary detection |
| 1.4 | MCP Health Checks | `a2a_hub/mcp_server/server.py` | Ping/health endpoint for monitoring |
| 1.5 | Tauri Wayland Fix | `src-tauri/` | Fix empty window (NVIDIA+WebKitGTK workaround) |

**Deliverables:**
- MCP server with rate limiting + validation
- Semantic chunking in RAG
- Tauri window renders React content on Wayland

---

### M2: Hybrid Search + Re-ranking (P0 — Weeks 2-3)

**Цель**: 25-40% precision improvement in retrieval

| # | Task | Files | Description |
|---|------|-------|-------------|
| 2.1 | BM25 Index | `agent/rag.py` | Add BM25 via `rank_bm25` (pure Python, no deps) |
| 2.2 | RRF Fusion | `agent/rag.py` | Reciprocal Rank Fusion: BM25 top-50 + Vector top-50 → merged top-50 |
| 2.3 | Cross-Encoder Re-ranker | `agent/rag.py` | `cross-encoder/ms-marco-MiniLM-L-6-v2` (self-hosted, 89MB) |
| 2.4 | Pipeline Orchestration | `agent/rag.py` | Query → Hybrid(top-50) → Rerank(top-5) → LLM |
| 2.5 | RAGAS Evaluation | `tests/test_rag.py` | faithfulness, relevance, precision metrics |

**Architecture:**
```
Query → [BM25(top-50) ⊕ Vector(top-50)] → RRF Fusion(top-50) → Cross-Encoder(top-5) → LLM
```

**Deliverables:**
- Hybrid search with BM25 + vector
- Re-ranking pipeline
- RAGAS evaluation suite

---

### M3: Agentic RAG (P0 — Weeks 4-5)

**Цель**: RAG accuracy 85% → 95%+ recall@5

| # | Task | Files | Description |
|---|------|-------|-------------|
| 3.1 | Query Transformation | `agent/rag.py` | HyDE (Hypothetical Document Embeddings), multi-query expansion |
| 3.2 | Iterative Retrieval | `agent/agent_loop.py` | Agent evaluates context sufficiency → re-retrieves if needed |
| 3.3 | Query Decomposition | `agent/rag.py` | Break complex queries into sub-queries, merge results |
| 3.4 | Agent Evaluation Step | `agent/agent_loop.py` | After retrieval: "Is this sufficient? What's missing?" |

**Pipeline:**
```
Query → Transform(HyDE, Multi-Query) → Hybrid Search → Rerank → 
  Agent Evaluates → [Sufficient? → LLM | Insufficient → Reformulate → Re-retrieve]
```

**Deliverables:**
- Iterative retrieval loop
- Query transformation pipeline
- Agent self-evaluation of retrieval quality

---

### M4: Reflexion Pattern (P1 — Weeks 6-7)

**Цель**: Self-correcting agent that learns from mistakes

| # | Task | Files | Description |
|---|------|-------|-------------|
| 4.1 | ReflectionMemory | `agent/reflection.py` | Store lessons from past failures (inspired by Kilo Code's session compaction) |
| 4.2 | Step Evaluator | `agent/agent_loop.py` | After each tool call: evaluate success/relevance |
| 4.3 | Reflection Prompt | `agent/context_manager.py` | Add reflection template to system prompt |
| 4.4 | Error Analysis | `agent/agent_loop.py` | On failure: analyze → reflect → retry with new approach |

**Pattern (from Kilo Code research):**
```
Act → Evaluate → [Success → Continue | Fail → Reflect → Plan → Retry]
         │
         ▼
    ReflectionMemory
    "Failed because X, next time try Y"
```

**Deliverables:**
- ReflectionMemory module
- Self-correcting agent loop
- Reflection-augmented system prompt

---

### M5: Multi-Agent Architecture v2 (P1 — Weeks 8-10)

**Цель**: True multi-agent orchestration with specialized agents

| # | Task | Files | Description |
|---|------|-------|-------------|
| 5.1 | Agent Base Class Refactor | `agent/agent_loop.py` | Extract BaseAgent from AgentLoop |
| 5.2 | Orchestrator v2 | `a2a_hub/orchestrator.py` | DAG planner + dependency resolver + parallel executor |
| 5.3 | Code Agent | `a2a_hub/agents/code_agent.py` | read/write/edit/search specialization |
| 5.4 | Search Agent | `a2a_hub/agents/search_agent.py` | codebase + web + RAG specialization |
| 5.5 | Analysis Agent | `a2a_hub/agents/analysis_agent.py` | system_monitor + diagnostic specialization |
| 5.6 | Test Agent | `a2a_hub/agents/test_agent.py` | pytest + cargo test specialization |
| 5.7 | Capability Router | `a2a_hub/router.py` | Classify task → select best agent(s) |
| 5.8 | Agent Manager UI | `plasmoid/.../A2AChatView.qml` | Multi-agent panel (inspired by Kilo Code AgentManager) |

**Inspired by Kilo Code's AgentManager:**
- Each agent runs in isolated context (no shared state)
- Orchestrator delegates via HTTP (A2A Hub protocol)
- Parallel execution for independent tasks
- Results aggregated by Orchestrator

**Deliverables:**
- 4 specialized agents + orchestrator
- Capability-based routing
- Agent Manager UI in QML + React

---

### M6: Plugin System (P1 — Weeks 11-12)

**Цель**: Extensible tool ecosystem

| # | Task | Files | Description |
|---|------|-------|-------------|
| 6.1 | Plugin Interface | `agent/plugin.py` | Abstract base class: `name`, `description`, `execute()`, `schema()` |
| 6.2 | Plugin Manager | `agent/plugin_manager.py` | Load, validate, lifecycle management |
| 6.3 | Plugin Discovery | `agent/plugin_manager.py` | Scan `plugins/` directory, auto-register |
| 6.4 | Migrate Existing Tools | `agent/tools.py` | Convert 12 built-in tools to plugins |
| 6.5 | Example Plugin | `plugins/example/` | Reference implementation |
| 6.6 | Plugin SDK Docs | `docs/plugin-sdk.md` | Developer documentation |

**Plugin Structure:**
```
plugins/
├── my_plugin/
│   ├── __init__.py  # Plugin class
│   ├── schema.json   # Tool schema
│   └── README.md     # Documentation
```

**Deliverables:**
- Plugin interface + manager
- All 12 tools migrated to plugins
- SDK documentation

---

### M7: MCP Security Hardening (P0 — Week 1, parallel)

**Цель**: Secure MCP server against abuse

| # | Task | Files | Description |
|---|------|-------|-------------|
| 7.1 | Input Validation | `a2a_hub/mcp_server/server.py` | JSON Schema validation for all inputs |
| 7.2 | Rate Limiting | `a2a_hub/mcp_server/server.py` | Token bucket per agent/method |
| 7.3 | Sandboxing | `a2a_hub/mcp_server/server.py` | Run MCP servers in isolated subprocess |
| 7.4 | Audit Logging | `a2a_hub/mcp_server/server.py` | Structured audit log for all MCP calls |
| 7.5 | Permission System | `a2a_hub/mcp_server/permissions.py` | Tool-level permissions (inspired by Kilo Code) |

**Deliverables:**
- Rate-limited MCP server
- Input validation on all tools
- Audit logging

---

### M8: GPU Acceleration (P2 — Weeks 13-18)

**Цель**: 10x faster embedding generation

| # | Task | Files | Description |
|---|------|-------|-------------|
| 8.1 | CUDA batch_normalize | `src/embedding.cpp` | CUDA kernel for batch normalization |
| 8.2 | CUDA similarity_matrix | `src/embedding.cpp` | CUDA kernel for similarity computation |
| 8.3 | Batched Embedding Inference | `agent/rag.py` | GPU-accelerated embedding generation |
| 8.4 | cuBLAS Integration | `CMakeLists.txt` | BLAS optimizations for matrix ops |

**Deliverables:**
- CUDA-accelerated embedding pipeline
- 10x throughput improvement

---

## 5. Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| RAG recall@5 | ~85% | >95% | RAGAS evaluation |
| RAGAS faithfulness | — | >0.9 | RAGAS evaluation |
| Hybrid search precision | — | +25-40% | Manual evaluation |
| Agent task completion | ~70% | >90% | Task success rate |
| Agent self-correction | 0% | >50% | Reflexion success rate |
| MCP server uptime | — | >99.9% | Health check monitoring |
| Plugin ecosystem | 0 | >5 | Community contributions |
| GPU embedding throughput | CPU-only | 10x | Benchmark |
| Multi-agent parallel speedup | 1x | 3-4x | Parallel task execution |

---

## 6. Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Agentic RAG increases latency 3-5x | High | Medium | Async retrieval, caching, budget limits |
| Multi-agent debugging complexity | Medium | High | Structured logging, OpenObserve tracing |
| Plugin security vulnerabilities | Medium | High | Sandboxing, permission system, audit |
| GPU code not portable | Low | Medium | CUDA + CPU fallback paths |
| Tauri Wayland issues persist | Medium | Medium | Fallback to XWayland, or switch to QML-only |
| Token costs increase with Reflexion | High | Medium | Budget tracking, configurable limits |

---

## 7. Recommended Execution Order

```
Week 1:     M1 (Quick Wins) + M7 (MCP Security) — parallel
Week 2-3:   M2 (Hybrid Search + Re-ranking)
Week 4-5:   M3 (Agentic RAG)
Week 6-7:   M4 (Reflexion Pattern)
Week 8-10:  M5 (Multi-Agent v2)
Week 11-12: M6 (Plugin System)
Week 13+:   M8 (GPU Acceleration)
```

---

## 8. File Changes Map

### New Files

| File | Purpose | Milestone |
|------|---------|-----------|
| `agent/reflection.py` | ReflectionMemory + StepEvaluator | M4 |
| `agent/plugin.py` | Plugin interface (ABC) | M6 |
| `agent/plugin_manager.py` | Plugin discovery + lifecycle | M6 |
| `a2a_hub/agents/code_agent.py` | Code specialist agent | M5 |
| `a2a_hub/agents/search_agent.py` | Search specialist agent | M5 |
| `a2a_hub/agents/analysis_agent.py` | Analysis specialist agent | M5 |
| `a2a_hub/agents/test_agent.py` | Test specialist agent | M5 |
| `a2a_hub/router.py` | Capability-based task router | M5 |
| `a2a_hub/mcp_server/permissions.py` | MCP permission system | M7 |
| `plugins/example/` | Example plugin | M6 |
| `docs/plugin-sdk.md` | Plugin developer docs | M6 |

### Modified Files

| File | Changes | Milestone |
|------|---------|-----------|
| `agent/rag.py` | BM25, RRF, re-ranking, iterative retrieval, semantic chunking | M2, M3 |
| `agent/agent_loop.py` | Reflexion, iterative retrieval integration | M3, M4 |
| `agent/context_manager.py` | Reflection prompt template | M4 |
| `agent/tools.py` | Plugin interface migration | M6 |
| `a2a_hub/orchestrator.py` | DAG planner, parallel executor | M5 |
| `a2a_hub/mcp_server/server.py` | Rate limiting, validation, audit | M1, M7 |
| `plasmoid/.../A2AChatView.qml` | Agent Manager UI | M5 |
| `src/components/ChatView.tsx` | Multi-agent display | M5 |
| `tests/test_rag.py` | RAGAS evaluation tests | M2 |
| `tests/test_reflection.py` | Reflexion tests | M4 |
| `tests/test_plugin.py` | Plugin system tests | M6 |

---

## 9. Kilo Code Patterns to Adopt

| Pattern | Kilo Code Source | Our Implementation |
|---------|-----------------|-------------------|
| Subagent delegation | `tool/task.ts` | Orchestrator → specialist agents |
| Worktree isolation | `WorktreeManager` | Git worktree per agent (optional) |
| Multi-model comparison | `multi-version.ts` | A2A Hub multi-model routing |
| Permission system | `permission/evaluate.ts` | MCP permission layer |
| Compaction | `session/compaction.ts` | Context compression in AgentLoop |
| Agent Manager UI | `AgentManagerProvider.tsx` | QML + React multi-agent panel |
| AGENTS.md convention | `AGENTS.md` | Project-level agent instructions |
| kilocode_change markers | Fork merge strategy | If we fork upstream tools |

---

*Plan created: 2026-05-28*
*Research sources: Kilo Code source analysis, A2A Hub codebase audit, RAG/AgentLoop review, plans-and-recommendations.md v1.2.1*
