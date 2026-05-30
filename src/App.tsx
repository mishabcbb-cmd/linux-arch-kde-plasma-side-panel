/**
 * src/App.tsx — Main application component for AI Agent Panel.
 *
 * React + Tauri integration:
 *   • Tauri commands invoke Python D-Bus helper (run_task, get_status, stop_task, etc.)
 *   • Tauri events receive D-Bus signals from Rust subprocess (dbus_listener.py)
 *   • Zustand store manages all UI state (replacing QML property system)
 */

import { useCallback, useEffect } from "react";
import { useAgentStore } from "./store/agentStore";
import type { AgentStatus, MessageType } from "./types";
import ChatView from "./components/ChatView";
import TaskInput from "./components/TaskInput";
import StatusBar from "./components/StatusBar";
import FileTree from "./components/FileTree";

// ── Tauri imports (available at runtime via Tauri WebView) ──
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { UnlistenFn } from "@tauri-apps/api/event";

// ── Tauri command response types ──
interface AgentStatusResponse {
  status: string;
  connected: boolean;
}

interface CommandResponse {
  success: boolean;
  message: string;
}

export default function App() {
  const connected = useAgentStore((s) => s.connected);
  const contextFiles = useAgentStore((s) => s.contextFiles);
  const removeContextFile = useAgentStore((s) => s.removeContextFile);
  const clearMessages = useAgentStore((s) => s.clearMessages);
  const setStatus = useAgentStore((s) => s.setStatus);
  const setConnected = useAgentStore((s) => s.setConnected);
  const addMessage = useAgentStore((s) => s.addMessage);
  const appendToken = useAgentStore((s) => s.appendToken);
  const addContextFile = useAgentStore((s) => s.addContextFile);
  const fileTreeOpen = useAgentStore((s) => s.fileTreeOpen);
  const setFileTreeOpen = useAgentStore((s) => s.setFileTreeOpen);

  // ── Listen for D-Bus signals from Rust subprocess ──
  useEffect(() => {
    let unlisten: UnlistenFn | null = null;

    const setupListener = async () => {
      try {
        unlisten = await listen("dbus-signal", (event) => {
          const msg = event.payload as Record<string, unknown>;
          const signalType = msg.signal as string;
          handleDbusSignal(signalType, msg);
        });
        log.info("D-Bus signal listener attached");
      } catch (e) {
        log.error("Failed to attach D-Bus signal listener:", e);
      }
    };

    setupListener();

    // Check initial connection status
    checkConnection();

    // Periodic connection check (every 5s)
    const interval = setInterval(checkConnection, 5000);

    return () => {
      if (unlisten) unlisten();
      clearInterval(interval);
    };
  }, []);

  // ── Check agent connection status ──
  const checkConnection = useCallback(async () => {
    try {
      const result = await invoke<boolean>("check_agent_connected");
      setConnected(result);
    } catch {
      setConnected(false);
    }
  }, [setConnected]);

  // ── D-Bus signal handler (mirrors QML handleDbusSignal) ──
  const handleDbusSignal = useCallback(
    (signalType: string, msg: Record<string, unknown>) => {
      setConnected(true);

      switch (signalType) {
        case "_listener_started":
          refreshStatus();
          break;

        case "StatusChanged":
          setStatus(((msg.status as string) || "idle") as AgentStatus);
          break;

        case "TokenStream":
          appendToken(
            (msg.content as string) || "",
            ((msg.msg_type as string) || "thought") as MessageType
          );
          break;

        case "ToolCallStarted":
          addMessage({
            type: "tool_call",
            toolName: (msg.tool_name as string) || "Tool",
            content:
              typeof msg.input === "string"
                ? msg.input
                : JSON.stringify(msg.input || {}, null, 2),
            iteration: (msg.iteration as string) || "0",
          });
          setStatus("executing");
          break;

        case "ToolCallResult":
          addMessage({
            type: "tool_result",
            toolName: (msg.tool_name as string) || "Tool",
            content: ((msg.output as string) || "").substring(0, 2000),
            // @ts-expect-error — success field from D-Bus
            success: msg.success !== false,
          });
          break;

        case "TaskComplete":
          addMessage({
            type: "task_complete",
            content: "✅ Task complete",
          });
          setStatus("idle");
          break;

        case "ErrorOccurred":
          addMessage({
            type: "error",
            content: (msg.error as string) || "Unknown error",
          });
          setStatus("error");
          break;

        case "QuestionAsked":
          addMessage({
            type: "question",
            content: (msg.question as string) || "",
            options:
              typeof msg.options === "string"
                ? JSON.parse(msg.options)
                : msg.options || [],
          });
          setStatus("waiting_user");
          break;

        case "_service_stopped":
          setConnected(false);
          setStatus("error");
          break;

        case "_service_started":
          setConnected(true);
          refreshStatus();
          break;

        case "_listener_stopped":
          log.warn("D-Bus listener stopped");
          addMessage({
            type: "error",
            content: "⚠️ D-Bus signal listener disconnected. Restart Tauri to reconnect.",
          });
          break;

        default:
          log.debug("Unhandled D-Bus signal:", signalType, msg);
      }
    },
    [setConnected, setStatus, addMessage, appendToken]
  );

  // ── Refresh agent status via Tauri command ──
  const refreshStatus = useCallback(async () => {
    try {
      const result = await invoke<AgentStatusResponse>("get_agent_status");
      setStatus(result.status as AgentStatus);
      setConnected(result.connected);
    } catch (e) {
      log.warn("Failed to get agent status:", e);
      setConnected(false);
    }
  }, [setStatus, setConnected]);

  // ── Send task via Tauri command ──
  const handleSendTask = useCallback(
    async (task: string) => {
      addMessage({ type: "thought", content: `🧑 You: ${task}` });
      setStatus("thinking");

      try {
        const result = await invoke<CommandResponse>("run_task", {
          task,
          fileContext: contextFiles,
        });
        if (!result.success) {
          addMessage({ type: "error", content: result.message });
          setStatus("error");
        }
      } catch (e) {
        addMessage({
          type: "error",
          content: `Failed to send task: ${e}`,
        });
        setStatus("error");
      }
    },
    [addMessage, setStatus, contextFiles]
  );

  // ── Stop task via Tauri command ──
  const handleStop = useCallback(async () => {
    try {
      await invoke<CommandResponse>("stop_task");
      setStatus("idle");
    } catch (e) {
      log.warn("Failed to stop task:", e);
    }
  }, [setStatus]);

  // ── Provide user response via Tauri command ──
  const handleProvideResponse = useCallback(
    async (response: string) => {
      addMessage({ type: "thought", content: `🧑 You: ${response}` });
      try {
        await invoke<CommandResponse>("provide_response", { response });
      } catch (e) {
        log.warn("Failed to provide response:", e);
      }
    },
    [addMessage]
  );

  // ── File tree selection ──
  const handleFilesSelected = useCallback(
    (paths: string[]) => {
      for (const p of paths) {
        addContextFile(p);
      }
      setFileTreeOpen(false);
    },
    [addContextFile, setFileTreeOpen]
  );

  return (
    <div
      className="h-screen w-full flex flex-col overflow-hidden select-none"
      style={{
        backgroundColor: "var(--bg-primary, #232629)",
        color: "var(--text-primary, #eff1f5)",
      }}
    >
      {/* ── Header ── */}
      <div
        className="flex items-center gap-2 px-3 py-2 border-b flex-shrink-0"
        style={{
          backgroundColor: "var(--bg-header, #2a2e32)",
          borderColor: "var(--border-color, rgba(255,255,255,0.1))",
        }}
      >
        <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          AI Agent
        </span>

        {/* Connection dot + status pushed to right before close button */}
        <div className="flex-1" />

        <div className="flex items-center gap-1.5">
          <div
            className="w-2 h-2 rounded-full"
            style={{
              backgroundColor: connected ? "#639922" : "#E24B4A",
              opacity: connected ? 1 : 0.5,
            }}
          />
          <span
            className="text-xs"
            style={{ color: "var(--text-disabled, #7f8c8d)" }}
          >
            {connected ? "Connected" : "Disconnected"}
          </span>
        </div>

        {/* Close button — far right */}
        <button
          className="p-1 rounded hover:opacity-80 transition-colors ml-1"
          style={{ color: "var(--text-secondary)" }}
          title="Close"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {/* ── Chat messages — fills all available space ── */}
      <ChatView
        onProvideUserResponse={handleProvideResponse}
        onStop={handleStop}
      />

      {/* ── Context file chips ── */}
      {contextFiles.length > 0 && (
        <div className="flex flex-wrap gap-1 px-3 py-1 border-t flex-shrink-0" style={{ borderColor: "var(--border-color)" }}>
          {contextFiles.map((file) => (
            <span
              key={file}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs"
              style={{
                backgroundColor: "rgba(61, 174, 233, 0.1)",
                border: "1px solid rgba(61, 174, 233, 0.3)",
                color: "#3DAEE9",
              }}
            >
              <span className="truncate max-w-[150px]">{file.split("/").pop() || file}</span>
              <button
                onClick={() => removeContextFile(file)}
                className="hover:opacity-70 flex-shrink-0"
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </span>
          ))}
        </div>
      )}

      {/* ── Input area ── */}
      <TaskInput onSendTask={handleSendTask} />

      {/* ── Status bar ── */}
      <StatusBar
        onStop={handleStop}
        onClear={clearMessages}
        onToggleFileTree={() => setFileTreeOpen(true)}
      />

      {/* ── File tree overlay ── */}
      {fileTreeOpen && (
        <FileTree
          onClose={() => setFileTreeOpen(false)}
          onFilesSelected={handleFilesSelected}
        />
      )}
    </div>
  );
}

// ── Logging helper ──
const log = {
  info: (...args: unknown[]) => console.log("[App]", ...args),
  warn: (...args: unknown[]) => console.warn("[App]", ...args),
  error: (...args: unknown[]) => console.error("[App]", ...args),
  debug: (...args: unknown[]) => console.debug("[App]", ...args),
};
