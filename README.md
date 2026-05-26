# KDE AI Agent Panel

An AI coding agent embedded in a KDE Plasma 6 desktop panel. Chat with **Claude** or **local Ollama** models to read, write, search, and test code — all from your desktop sidebar.

![Status](https://img.shields.io/badge/status-alpha-orange)
![KDE Plasma](https://img.shields.io/badge/KDE%20Plasma-6-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)

## Features

- **ReAct Agent Loop** — Reason + Act pattern: the agent thinks, calls tools, reads results, and iterates
- **Streaming Output** — Tokens stream to the QML chat view in real time (like end4's AI sidebar)
- **Multi-Provider** — Switch between Anthropic Claude API and local Ollama in settings
- **7 Built-in Tools** — `bash_exec`, `file_read`, `file_write`, `search_codebase`, `repo_map`, `run_tests`, `ask_user`
- **Auto Git Commits** — Every file write is auto-committed with a descriptive message
- **D-Bus Integration** — QML UI communicates with Python backend over D-Bus session bus
- **OpenObserve Ready** — Stream all agent events (tool calls, LLM responses, errors) to OpenObserve
- **Context Files** — Select files to inject into the LLM context for targeted edits

## Architecture

```
┌───────────────────────────────────────────────────────┐
│  KDE Plasma Panel (QML)                              │
│  ┌─────────┐ ┌──────────┐ ┌────────┐ ┌───────────┐  │
│  │ ChatView│ │TaskInput │ │FileTree│ │ StatusBar │  │
│  └────┬────┘ └────┬─────┘ └───┬────┘ └─────┬─────┘  │
│       │           │           │             │         │
│       └───────────┴───────────┴─────────────┘         │
│                       │ D-Bus                        │
├───────────────────────┼──────────────────────────────┤
│                       ▼                               │
│  Python Agent Backend (systemd user service)          │
│  ┌──────────┐ ┌────────────┐ ┌───────────────────┐  │
│  │agent_loop│◄│llm_client  │◄│Anthropic / Ollama │  │
│  │(ReAct)   │ │(streaming) │ │(provider switch)  │  │
│  └────┬─────┘ └────────────┘ └───────────────────┘  │
│       │                                               │
│  ┌────┴─────┐ ┌──────────────┐ ┌─────────────────┐  │
│  │tools.py  │ │context_mgr   │ │main.py (D-Bus)  │  │
│  │7 tools   │ │token budget  │ │OpenObserve sink │  │
│  └──────────┘ └──────────────┘ └─────────────────┘  │
└───────────────────────────────────────────────────────┘
```

## Requirements

### System
- **Arch Linux** (or any system with `pacman`/`yay`)
- **KDE Plasma 6** (for the plasmoid widget)
- **Python 3.10+**
- **ripgrep** (`rg`) — for codebase search
- **git** — for auto-commits

### API Key (choose one)
- **Anthropic API key** → [console.anthropic.com](https://console.anthropic.com/)
- **Ollama** (local, free) → `pacman -S ollama && ollama serve`

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
3. Installs the plasmoid (`kpackagetool6 --install`)
4. Creates and starts a systemd user service for the agent backend
5. Creates a default config at `~/.config/kde-ai-agent/config.json`

## Configuration

Edit `~/.config/kde-ai-agent/config.json`:

```json
{
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "api_key": "sk-ant-api03-your-key-here",
    "ollama_host": "http://localhost:11434",
    "ollama_model": "llama3.2",
    "max_tokens": 8192,
    "temperature": 0.7,
    "working_dir": "/home/you/projects/my-project",
    "openobserve_endpoint": "",
    "openobserve_stream": "ai-agent-events"
}
```

### Switching to Ollama

```json
{
    "provider": "ollama",
    "model": "llama3.2",
    "ollama_host": "http://localhost:11434"
}
```

Make sure Ollama is running: `systemctl --user start ollama`

### OpenObserve (optional)

Set `openobserve_endpoint` to your OpenObserve URL (e.g., `http://localhost:5080`). All agent events will be streamed as structured JSON logs for real-time monitoring and dashboarding.

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
- Browse and select files to add context
- Selected files appear as chips above the input
- Click chips to remove

### Keybinds
| Key | Action |
|-----|--------|
| `Ctrl+Enter` | Send task |
| `Esc` | Clear input |

## Tool Reference

The agent has these tools available:

| Tool | Description |
|------|-------------|
| `bash_exec` | Run shell commands (build, test, git, system) |
| `file_read` | Read files with line numbers |
| `file_write` | Write/create files with auto git commit |
| `search_codebase` | Regex search across all project files (ripgrep) |
| `repo_map` | Generate tree-sitter structural codebase summary |
| `run_tests` | Auto-detect test framework and run tests |
| `ask_user` | Pause and ask you a question via the UI |

## Development

### Project Structure

```
linux-arch-kde-plasma-side-panel/
├── agent/                          # Python backend
│   ├── __init__.py
│   ├── main.py                     # D-Bus service entry point
│   ├── agent_loop.py               # ReAct loop core
│   ├── tools.py                    # 7 tool implementations
│   ├── llm_client.py               # Provider abstraction
│   ├── context_manager.py          # Token budget management
│   └── requirements.txt
├── plasmoid/ai-agent-panel/        # QML plasmoid
│   ├── metadata.json               # Plasma 6 package metadata
│   └── contents/
│       ├── ui/
│       │   ├── main.qml            # Root panel
│       │   ├── ChatView.qml        # Streaming chat log
│       │   ├── TaskInput.qml       # Multi-line input
│       │   ├── FileTree.qml        # File context picker
│       │   └── StatusBar.qml       # Status + action buttons
│       └── config/
│           ├── config.qml          # Settings root
│           ├── ConfigApi.qml       # API provider settings
│           ├── ConfigDirectory.qml # Working directory
│           └── ConfigAdvanced.qml  # Token limits, OpenObserve
├── install.sh
├── uninstall.sh
└── README.md
```

### Running the Backend Manually

```bash
cd agent
python3 -m agent.main
```

### Testing D-Bus

```bash
# Check service is running
systemctl --user status kde-ai-agent

# Query status
qdbus org.kde.aiagent /org/kde/aiagent org.kde.aiagent.GetStatus

# Run a task
qdbus org.kde.aiagent /org/kde/aiagent org.kde.aiagent.RunTask "Create hello.txt" "[]"
```

### Viewing Logs

```bash
journalctl --user -u kde-ai-agent -f
```

## Uninstall

```bash
chmod +x uninstall.sh
./uninstall.sh
```

## License

GPL-3.0 — See [LICENSE](LICENSE)

## Credits

Patterns and inspiration from:
- **JARVIS** (novik133/jarvis) — KDE Plasma 6 plasmoid structure
- **end4** (dots-hyprland) — AI sidebar streaming pattern
- **Aider** (Aider-AI/aider) — ReAct loop + repo map
- **OpenCode** (opencode-ai/opencode) — Provider abstraction
- **ZooCode / Roo Code** — Tool execution interface
