# UI Redesign Task — AI Agent Panel (React/Tauri)

## Context
The current React frontend (`src/App.tsx` and component files) renders incorrectly.
All content collapses to the top ~220px of the window. The chat area has no height.
The toolbar buttons have no labels. The layout does not use the available vertical space.

This task is ONLY about the React UI. Do NOT touch:
- Any Python backend files
- Any Rust/Tauri backend files
- D-Bus bridge code
- Agent logic
- `tauri.conf.json` window size (keep it as-is)

---

## Target Layout

The panel must be a full-height flex column with exactly these sections top to bottom:

```
┌─────────────────────────────────┐
│ HEADER (fixed height ~42px)     │
├─────────────────────────────────┤
│                                 │
│ CHAT AREA (flex: 1)             │
│ scrollable, fills all space     │
│                                 │
├─────────────────────────────────┤
│ CONTEXT CHIPS (auto height)     │
├─────────────────────────────────┤
│ INPUT AREA (auto height)        │
├─────────────────────────────────┤
│ TOOLBAR (fixed height ~38px)    │
└─────────────────────────────────┘
```

---

## Section 1 — Root Layout (`App.tsx`)

The root container must be:
```css
display: flex;
flex-direction: column;
height: 100vh;
overflow: hidden;
background: var CSS variable for primary background
```

The chat area component must have:
```css
flex: 1;
overflow-y: auto;
min-height: 0;   /* CRITICAL — without this flexbox won't shrink it */
padding: 12px 14px;
display: flex;
flex-direction: column;
gap: 10px;
```

---

## Section 2 — Header

Single row, `flex-shrink: 0`, height ~42px, with:

LEFT SIDE (flex row, gap 8px):
- Small green dot (7px circle, color #1D9E75) — connection indicator
- "AI Agent" — 14px, font-weight 500
- "connected" or "disconnected" — 12px, muted color

RIGHT SIDE (flex row, gap 2px):
- Settings button — gear icon (ti-settings), 28×28px icon button
- Close button — X icon (ti-x), 28×28px icon button

No other elements in the header. Remove any duplicate status text, welcome messages,
or descriptive subtitles ("Type a task below...", "The agent can read, write...").
These must be completely removed — they waste permanent space.

---

## Section 3 — Chat Area (`ChatView.tsx`)

Messages render in a flex column from top to bottom. Each message is one of:

### 3a. User message
- Aligned to RIGHT (`align-self: flex-end`)
- Label "You" in 11px muted text above the bubble
- Bubble: padding 8px 11px, border-radius md, background secondary, border tertiary 0.5px
- Max width: 90% of container

### 3b. Agent text message
- Aligned to LEFT (`align-self: flex-start`)
- Label "Agent" in 11px muted text above the bubble
- Same bubble style as user but left-aligned
- Max width: 92% of container

### 3c. Tool call chip
- Aligned LEFT, full width, no bubble
- Monospace font, 11px
- Padding: 5px 9px, border-radius md, border 0.5px
- Three states with different colors:
  - Running: amber text (#BA7517), amber border (#EF9F27), loader icon (ti-loader-2)
  - Done: teal text (#0F6E56), teal border (#5DCAA5), check icon (ti-check)
  - Error: red text (#A32D2D), red border (#F09595), x icon (ti-x)
- Format: `tool_name(args) — result or status`

### 3d. Reasoning block (collapsible) — THIS IS NEW
This replaces the current "Thinking..." text. It must be a collapsible component.

COLLAPSED STATE (default):
- Full-width button row, padding 5px 9px, border 0.5px border-tertiary, border-radius md
- Left side: brain icon (ti-brain, 14px) + "thinking" text (11px muted)
- Animated dots (3 dots, CSS animation, opacity blink, 1.2s cycle, staggered 0.2s)
- Right side: chevron-down icon (ti-chevron-down, 13px)
- When agent is still thinking: show animated dots
- When agent finished thinking: replace dots with token count e.g. "482 tokens", hide dots

EXPANDED STATE (after clicking):
- Toggle button rotates chevron 180deg
- Dots hide (user is reading the content, no need for animation)
- Body appears below the toggle button:
  - Max height: 180px, overflow-y: auto
  - Monospace font, 11.5px, line-height 1.65
  - Background secondary, border 0.5px tertiary, border-radius md
  - Padding: 8px 11px
  - Contains the raw reasoning/thinking text streamed from the model

Click toggle again → collapses back, dots reappear if still thinking.

Each reasoning block is independent — collapsing one does not affect others.

---

## Section 4 — Context File Chips

Shown only when `contextFiles.length > 0`. Otherwise hidden (not just invisible — `display: none`).

Horizontal flex row, `flex-wrap: wrap`, gap 6px, padding 6px 14px.

Each chip:
- Pill shape (border-radius 99px)
- 11px text, muted color
- Background secondary, border tertiary 0.5px
- file icon (ti-file-code) + filename (basename only, not full path)
- Clicking a chip removes that file from context

---

## Section 5 — Input Area

`flex-shrink: 0`, padding 10px 14px, border-top 0.5px tertiary.

Flex row, gap 8px, align-items flex-end:

TEXTAREA:
- `flex: 1`
- min-height: 60px, max-height: 120px
- resize: none
- font-size 13px, line-height 1.5
- border 0.5px tertiary, border-radius md
- placeholder: "Describe your task… (Ctrl+Enter to send)"
- On focus: border brightens to secondary
- Ctrl+Enter sends the task

SEND BUTTON:
- 34×34px, border-radius md
- When textarea is empty: muted style (secondary bg, tertiary border)
- When textarea has text: active style (green bg #1D9E75, white icon)
- Icon: ti-send, 16px
- `align-self: flex-end` so it sits at the bottom of the row

ATTACH BUTTON (optional, next to send):
- 34×34px, same muted style always
- Icon: ti-paperclip, 16px
- Opens file picker to add context files

---

## Section 6 — Toolbar

`flex-shrink: 0`, height ~38px, padding 7px 14px, border-top 0.5px tertiary.

Single flex row, `justify-content: space-between`.

LEFT SIDE — action buttons (flex row, gap 2px):
Each button is 28×28px, border-radius md, no border, transparent bg, muted icon color.
Hover: secondary background, primary icon color.

Buttons in order:
1. Stop — ti-player-stop — stops the current running task
2. Clear — ti-trash — clears the chat history
3. Terminal — ti-terminal-2 — opens terminal (existing behavior)
4. Files — ti-folder-open — opens file tree (existing behavior)

No text labels on these buttons. Use `aria-label` for accessibility only.

RIGHT SIDE — status info (flex row, gap 5px):
- CPU icon (ti-cpu, 13px, muted)
- Text: "iteration N · N tool calls" — 11px, muted
- Update this in real time as the agent runs

---

## Section 7 — Settings Panel

When the settings gear icon is clicked, a settings drawer slides in FROM THE RIGHT
over the main panel content (not replacing it). It should be:

- Position: absolute, top 0, right 0, width 100%, height 100%
- Background: primary bg, border-left 0.5px tertiary
- z-index above chat
- Slide animation: transform translateX(100%) → translateX(0), 200ms ease

Settings content (vertical list, padding 16px):

Header: "Settings" title (16px, 500) + X close button (right-aligned)

Sections:
1. Provider
   - Label: "LLM Provider"
   - Dropdown/select: "llama.cpp" | "Anthropic" | "Ollama" | "OpenRouter"

2. API / Host
   - Label: "Host URL" (shown for llama.cpp/Ollama)
   - Text input, current value from config

3. Model
   - Label: "Model"
   - Text input, current value from config

4. Working Directory
   - Label: "Working directory"
   - Text input with folder browse button

5. Max iterations
   - Label: "Max iterations"
   - Number input, default 50

Save button at the bottom — calls the existing `save_config` Tauri command.

---

## D-Bus / Tauri Event Wiring

The existing event wiring must remain intact. Map events to the new components:

| Tauri event | Target component | Action |
|---|---|---|
| `status-changed` | Header dot + toolbar status | Update color and text |
| `token-stream` | ChatView | Append to last agent bubble or create new one |
| `thinking-delta` | Reasoning block | Stream text into the expanded reasoning body |
| `tool-call-started` | ChatView | Add tool chip in "running" state |
| `tool-call-result` | ChatView | Update that chip to "done" or "error" |
| `task-complete` | Header + toolbar | Set status to idle |
| `error-occurred` | ChatView | Add error message bubble |

Streaming behavior for agent bubbles:
- When `token-stream` arrives and the last message is NOT an agent bubble → create a new agent bubble
- When `token-stream` arrives and the last message IS an agent bubble → append to it
- Do not create a new bubble for every token — accumulate within the same bubble

Streaming behavior for reasoning:
- When `thinking-delta` arrives → create a reasoning block if none exists for current turn
- Stream text into the reasoning body
- When thinking ends → replace animated dots with token count

---

## Files to modify

- `src/App.tsx` — root layout, event wiring, state management
- `src/components/ChatView.tsx` — message list, reasoning blocks, tool chips
- `src/components/TaskInput.tsx` — textarea + send/attach buttons
- `src/components/StatusBar.tsx` — toolbar row
- Add new: `src/components/ReasoningBlock.tsx` — collapsible reasoning component
- Add new: `src/components/SettingsPanel.tsx` — settings drawer

---

## What NOT to do

- Do NOT add welcome messages or descriptive text to the permanent UI
- Do NOT use inline styles for layout — use CSS modules or styled components consistently
- Do NOT show "Thinking..." as plain text — it must be the collapsible ReasoningBlock
- Do NOT create duplicate status indicators (one dot in header is enough)
- Do NOT break any existing Tauri command invocations or event listeners
- Do NOT change window dimensions in tauri.conf.json
- Do NOT touch any backend Python or Rust files

---

## Verification checklist

After implementing, confirm ALL of these:

- [ ] Chat area fills all available vertical space (flex: 1 + min-height: 0)
- [ ] Sending a task adds a user bubble on the RIGHT
- [ ] Agent response streams into a bubble on the LEFT
- [ ] Tool calls appear as color-coded chips (amber running, teal done, red error)
- [ ] Reasoning block appears collapsed by default with animated dots
- [ ] Clicking reasoning block expands it and shows the thinking text
- [ ] Clicking again collapses it
- [ ] Settings gear opens the settings drawer from the right
- [ ] Settings drawer has all 5 config fields and a save button
- [ ] Context file chips appear when files are added and disappear when removed
- [ ] Send button turns green when textarea has text
- [ ] Ctrl+Enter sends the task
- [ ] Toolbar shows real-time iteration and tool call count
- [ ] No welcome message or descriptive subtitle visible in the idle state
