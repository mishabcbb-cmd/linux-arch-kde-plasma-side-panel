"""
web/app.py — KDE AI Agent Web UI (FastAPI + HTMX).

Provides a browser-based interface for the agent when running
outside of KDE Plasma (headless/Docker mode).

Usage:
    python -m web.app
    # → http://localhost:8080

Requires: pip install fastapi uvicorn jinja2 httpx
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Lazy import agent — only if available
try:
    from agent.agent_loop import AgentLoop, AgentSignalType
    from agent.main import load_config
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False

logger = logging.getLogger(__name__)

app = FastAPI(title="KDE AI Agent Web UI")

# Templates
HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))

# Agent state
agent_instance: Optional[AgentLoop] = None
chat_messages: List[Dict[str, Any]] = []
agent_status: str = "idle"


# ── Agent Signal Handler ──

def signal_handler(signal_type: AgentSignalType, data: Dict[str, Any]) -> None:
    """Handle agent signals — append to chat messages."""
    global agent_status, chat_messages

    if signal_type == AgentSignalType.STATUS_CHANGED:
        agent_status = data.get("status", "idle")

    elif signal_type == AgentSignalType.TOKEN_STREAM:
        msg_type = data.get("type", "thought")
        content = data.get("content", "")
        if chat_messages and chat_messages[-1].get("type") == msg_type:
            chat_messages[-1]["content"] += content
        else:
            chat_messages.append({
                "type": msg_type,
                "content": content,
                "timestamp": None,
            })

    elif signal_type == AgentSignalType.TOOL_CALL_START:
        chat_messages.append({
            "type": "tool_call",
            "tool_name": data.get("tool_name", ""),
            "content": json.dumps(data.get("input", {}), indent=2),
            "timestamp": None,
        })

    elif signal_type == AgentSignalType.TOOL_CALL_RESULT:
        chat_messages.append({
            "type": "tool_result",
            "tool_name": data.get("tool_name", ""),
            "content": (data.get("output", "") or data.get("error", ""))[:500],
            "success": data.get("success", False),
            "timestamp": None,
        })

    elif signal_type == AgentSignalType.ERROR:
        chat_messages.append({
            "type": "error",
            "content": data.get("error", "Unknown error"),
            "timestamp": None,
        })
        agent_status = "error"

    elif signal_type == AgentSignalType.TASK_COMPLETE:
        agent_status = "complete"


# ── Routes ──

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main chat interface."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "messages": chat_messages[-50:],  # Last 50 messages
        "status": agent_status,
        "agent_available": AGENT_AVAILABLE,
    })


@app.post("/chat")
async def chat(request: Request, task: str = Form(...)):
    """Send a task to the agent."""
    global agent_instance

    if not AGENT_AVAILABLE:
        chat_messages.append({
            "type": "error",
            "content": "Agent module not available. Install with: pip install -e .",
        })
        return templates.TemplateResponse("partials/messages.html", {
            "request": request,
            "messages": chat_messages[-50:],
        })

    if agent_instance is None:
        config = load_config()
        agent_instance = AgentLoop(config)
        agent_instance.set_signal_handler(signal_handler)

    # Add user message
    chat_messages.append({
        "type": "user",
        "content": task,
        "timestamp": None,
    })

    # Run agent in background thread
    thread = threading.Thread(
        target=agent_instance.run_task,
        args=(task, []),
        daemon=True,
    )
    thread.start()

    return templates.TemplateResponse("partials/messages.html", {
        "request": request,
        "messages": chat_messages[-50:],
    })


@app.get("/stream")
async def stream_messages(request: Request):
    """SSE endpoint for streaming messages."""
    from fastapi.responses import StreamingResponse

    async def event_stream():
        last_count = len(chat_messages)
        while True:
            if len(chat_messages) > last_count:
                new_messages = chat_messages[last_count:]
                last_count = len(chat_messages)
                for msg in new_messages:
                    yield f"data: {json.dumps(msg)}\n\n"
            yield ": keepalive\n\n"
            import asyncio
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/status")
async def get_status():
    """Get current agent status."""
    return {
        "status": agent_status,
        "messages_count": len(chat_messages),
        "agent_available": AGENT_AVAILABLE,
    }


@app.post("/stop")
async def stop_task():
    """Stop the current task."""
    global agent_instance
    if agent_instance:
        agent_instance.stop_task()
    return {"status": "stopped"}


@app.post("/clear")
async def clear_chat():
    """Clear chat messages."""
    global chat_messages
    chat_messages = []
    return {"status": "cleared"}


# ── Main ──

def main():
    """Run the Web UI server."""
    import uvicorn
    print("=" * 50)
    print("  KDE AI Agent — Web UI")
    print(f"  http://localhost:8080")
    print(f"  Agent available: {AGENT_AVAILABLE}")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()
