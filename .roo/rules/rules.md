# lean-ctx: Mandatory Context Tool

lean-ctx is the primary context-saving and retrieval system. You MUST use it.

## On Every Task Start
- Call `ctx_overview` to load current project context before doing anything else.
- Call `ctx_read` to read relevant saved context for the task at hand.

## During Work
- Use `ctx_search` to find previously saved context before making assumptions.
- Use `ctx_knowledge` to retrieve stored knowledge about the codebase or project.

## On Every Task End
- Call `ctx_edit` to save any new context, decisions, or findings made during the task.
- Never end a task without persisting important context via lean-ctx.

## Rule
Never skip lean-ctx. It is not optional. It exists specifically to maintain
continuity between sessions — always read before working, always write after.

# Required MCP Tool Usage

## Memory & Context (MANDATORY)
- ALWAYS use `engram` tools to retrieve context at the start of every task:
  call `get_project_briefing` and `get_active_context` before doing any work.
- After completing work, log decisions with `log_decision` and progress with `log_progress`.
- NEVER rely solely on conversation history for project context — always query engram.

## Codebase Understanding (MANDATORY)
- Before editing or analyzing code, ALWAYS call `search_graph` or `search_code`
  via `codebase-memory-mcp` to understand the existing structure.
- Use `get_architecture` when asked about system design.
- Use `get_code_snippet` to read specific code before modifying it.

## Web Search
- Use `searxng` `search_web` for any research, library lookups, or current information.

## General Rule
- Prefer MCP tools over assumptions. If an MCP tool can answer a question
  or provide context, use it — do not guess or rely on training knowledge alone.
