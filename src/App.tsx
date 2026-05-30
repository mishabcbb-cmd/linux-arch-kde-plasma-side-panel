/**
 * src/App.tsx — Main application component for AI Agent Panel.
 *
 * Layout reference: ai_messenger_layout_v2.html
 */

import { useCallback, useEffect, useState } from "react";
import { useAgentStore } from "./store/agentStore";
import type { AgentStatus, MessageType } from "./types";
import ChatView from "./components/ChatView";
import TaskInput from "./components/TaskInput";
import StatusBar from "./components/StatusBar";
import FileTree from "./components/FileTree";

import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { UnlistenFn } from "@tauri-apps/api/event";

interface AgentStatusResponse { status: string; connected: boolean }
interface CommandResponse { success: boolean; message: string }

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
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    let unlisten: UnlistenFn | null = null;
    const setup = async () => {
      try {
        unlisten = await listen("dbus-signal", (event) => {
          const msg = event.payload as Record<string, unknown>;
          handleDbusSignal(msg.signal as string, msg);
        });
      } catch (e) { log.error("D-Bus listener failed:", e); }
    };
    setup();
    checkConnection();
    const interval = setInterval(checkConnection, 5000);
    return () => { if (unlisten) unlisten(); clearInterval(interval); };
  }, []);

  const checkConnection = useCallback(async () => {
    try { setConnected(await invoke<boolean>("check_agent_connected")); }
    catch { setConnected(false); }
  }, [setConnected]);

  const handleDbusSignal = useCallback(
    (signalType: string, msg: Record<string, unknown>) => {
      setConnected(true);
      switch (signalType) {
        case "_listener_started": refreshStatus(); break;
        case "StatusChanged": setStatus(((msg.status as string) || "idle") as AgentStatus); break;
        case "TokenStream": appendToken((msg.content as string) || "", ((msg.msg_type as string) || "thought") as MessageType); break;
        case "ToolCallStarted":
          addMessage({ type: "tool_call", toolName: (msg.tool_name as string) || "Tool", content: typeof msg.input === "string" ? msg.input : JSON.stringify(msg.input || {}, null, 2), iteration: (msg.iteration as string) || "0" });
          setStatus("executing"); break;
        case "ToolCallResult":
          addMessage({ type: "tool_result", toolName: (msg.tool_name as string) || "Tool", content: ((msg.output as string) || "").substring(0, 2000), success: msg.success !== false }); break;
        case "TaskComplete": addMessage({ type: "task_complete", content: "✅ Task complete" }); setStatus("idle"); break;
        case "ErrorOccurred": addMessage({ type: "error", content: (msg.error as string) || "Unknown error" }); setStatus("error"); break;
        case "QuestionAsked": addMessage({ type: "question", content: (msg.question as string) || "", options: typeof msg.options === "string" ? JSON.parse(msg.options) : msg.options || [] }); setStatus("waiting_user"); break;
        case "_service_stopped": setConnected(false); setStatus("error"); break;
        case "_service_started": setConnected(true); refreshStatus(); break;
        case "_listener_stopped": addMessage({ type: "error", content: "⚠️ D-Bus listener disconnected" }); break;
      }
    }, [setConnected, setStatus, addMessage, appendToken]
  );

  const refreshStatus = useCallback(async () => {
    try { const r = await invoke<AgentStatusResponse>("get_agent_status"); setStatus(r.status as AgentStatus); setConnected(r.connected); }
    catch { setConnected(false); }
  }, [setStatus, setConnected]);

  const handleSendTask = useCallback(async (task: string) => {
    addMessage({ type: "user", content: task });
    setStatus("thinking");
    try {
      const r = await invoke<CommandResponse>("run_task", { task, fileContext: contextFiles });
      if (!r.success) { addMessage({ type: "error", content: r.message }); setStatus("error"); }
    } catch (e) { addMessage({ type: "error", content: `Failed: ${e}` }); setStatus("error"); }
  }, [addMessage, setStatus, contextFiles]);

  const handleStop = useCallback(async () => {
    try { await invoke<CommandResponse>("stop_task"); setStatus("idle"); }
    catch (e) { log.warn("Stop failed:", e); }
  }, [setStatus]);

  const handleProvideResponse = useCallback(async (response: string) => {
    addMessage({ type: "user", content: response });
    try { await invoke<CommandResponse>("provide_response", { response }); }
    catch (e) { log.warn("Response failed:", e); }
  }, [addMessage]);

  const handleFilesSelected = useCallback((paths: string[]) => {
    for (const p of paths) addContextFile(p);
    setFileTreeOpen(false);
  }, [addContextFile, setFileTreeOpen]);

  return (
    <div className="panel">
      {/* ── Header ── */}
      <div className="header">
        <div className="header-left">
          <div className="status-dot" style={{ background: connected ? "#1D9E75" : "#E24B4A" }} />
          <span className="header-title">AI Agent</span>
          <span className="status-label">{connected ? "connected" : "disconnected"}</span>
        </div>
        <div className="header-right">
          <button className="icon-btn" aria-label="Settings" title="Settings" onClick={() => setSettingsOpen(!settingsOpen)}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
          <button className="icon-btn" aria-label="Close" title="Close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      </div>

      {/* ── Chat ── */}
      <ChatView onProvideUserResponse={handleProvideResponse} onStop={handleStop} />

      {/* ── Chips ── */}
      {contextFiles.length > 0 && (
        <div className="chips">
          {contextFiles.map((file) => (
            <div className="chip" key={file}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <span>{file.split("/").pop() || file}</span>
              <button onClick={() => removeContextFile(file)} className="chip-remove" title="Remove">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── Input ── */}
      <TaskInput onSendTask={handleSendTask} />

      {/* ── Toolbar ── */}
      <StatusBar onStop={handleStop} onClear={clearMessages} onToggleFileTree={() => setFileTreeOpen(true)} />

      {/* ── Overlays ── */}
      {fileTreeOpen && <FileTree onClose={() => setFileTreeOpen(false)} onFilesSelected={handleFilesSelected} />}
      {settingsOpen && (
        <div className="overlay" onClick={() => setSettingsOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <span className="modal-title">Settings</span>
              <button className="icon-btn" onClick={() => setSettingsOpen(false)} aria-label="Close">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="modal-body">
              <p className="modal-text">Agent configuration goes here.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const log = {
  info: (...a: unknown[]) => console.log("[App]", ...a),
  warn: (...a: unknown[]) => console.warn("[App]", ...a),
  error: (...a: unknown[]) => console.error("[App]", ...a),
  debug: (...a: unknown[]) => console.debug("[App]", ...a),
};
