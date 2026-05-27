/**
 * src/components/StatusBar.tsx — Bottom status bar for the AI Agent panel.
 *
 * React equivalent of StatusBar.qml.
 * Shows: status indicator, connection status, action buttons.
 */

import { useAgentStore } from "../store/agentStore";
import type { AgentStatus } from "../types";

// ── Status color map (matches QML) ──
const STATUS_COLOR: Record<AgentStatus, string> = {
  idle: "#639922",
  thinking: "#3DAEE9",
  executing: "#EF9F27",
  complete: "#639922",
  error: "#E24B4A",
  waiting_user: "#3DAEE9",
};

// ── Status label map (matches QML) ──
const STATUS_LABEL: Record<AgentStatus, string> = {
  idle: "Ready",
  thinking: "Thinking...",
  executing: "Executing...",
  complete: "Complete",
  error: "Error",
  waiting_user: "Waiting for input",
};

interface StatusBarProps {
  onRun: () => void;
  onStop: () => void;
  onClear: () => void;
  onToggleFileTree: () => void;
}

export default function StatusBar({ onRun, onStop, onClear, onToggleFileTree }: StatusBarProps) {
  const status = useAgentStore((s) => s.status);
  const connected = useAgentStore((s) => s.connected);

  const isIdle = status === "idle" || status === "complete" || status === "error";
  const isBusy = status === "thinking" || status === "executing";

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 border-t"
      style={{
        borderColor: "var(--border-color, rgba(255,255,255,0.1))",
        height: "2.5rem",
      }}
    >
      {/* Status indicator */}
      <div className="flex items-center gap-1.5">
        <div
          className="w-2 h-2 rounded-full"
          style={{
            backgroundColor: STATUS_COLOR[status],
            animation: isBusy ? "pulse 1s ease-in-out infinite" : "none",
          }}
        />
        <span
          className="text-xs"
          style={{ color: "var(--text-disabled, #7f8c8d)" }}
        >
          {STATUS_LABEL[status]}
        </span>
      </div>

      {/* Connection indicator */}
      <div
        className="flex items-center"
        title={connected ? "Connected to agent" : "Agent not connected"}
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke={connected ? "#639922" : "#E24B4A"}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {connected ? (
            <>
              <path d="M5 12.55a11 11 0 0 1 14.08 0" />
              <path d="M1.42 9a16 16 0 0 1 21.16 0" />
              <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
              <line x1="12" y1="20" x2="12.01" y2="20" />
            </>
          ) : (
            <>
              <line x1="1" y1="1" x2="23" y2="23" />
              <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
              <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
              <path d="M10.71 5.05A16 16 0 0 1 22.56 9" />
              <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
              <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
              <line x1="12" y1="20" x2="12.01" y2="20" />
            </>
          )}
        </svg>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Action buttons */}
      <button
        onClick={onRun}
        disabled={!isIdle}
        className="p-1.5 rounded transition-colors disabled:opacity-30 hover:opacity-80"
        style={{ color: "var(--text-secondary)" }}
        title="Run Task"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="5 3 19 12 5 21 5 3" />
        </svg>
      </button>

      <button
        onClick={onStop}
        disabled={!isBusy}
        className="p-1.5 rounded transition-colors disabled:opacity-30 hover:opacity-80"
        style={{ color: "var(--text-secondary)" }}
        title="Stop Task"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="6" y="6" width="12" height="12" />
        </svg>
      </button>

      <button
        onClick={onClear}
        className="p-1.5 rounded transition-colors hover:opacity-80"
        style={{ color: "var(--text-secondary)" }}
        title="Clear Chat"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          <line x1="10" y1="11" x2="10" y2="17" />
          <line x1="14" y1="11" x2="14" y2="17" />
        </svg>
      </button>

      <button
        className="p-1.5 rounded transition-colors hover:opacity-80"
        style={{ color: "var(--text-secondary)" }}
        title="Open Terminal"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="4 17 10 11 4 5" />
          <line x1="12" y1="19" x2="20" y2="19" />
        </svg>
      </button>

      <button
        onClick={onToggleFileTree}
        className="p-1.5 rounded transition-colors hover:opacity-80"
        style={{ color: "var(--text-secondary)" }}
        title="Context Files"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
        </svg>
      </button>
    </div>
  );
}
