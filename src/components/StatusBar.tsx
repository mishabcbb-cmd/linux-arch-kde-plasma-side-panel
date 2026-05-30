/**
 * src/components/StatusBar.tsx — Bottom status bar for the AI Agent panel.
 *
 * React equivalent of StatusBar.qml.
 * Shows: connection status with label, action buttons with tooltips.
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
  executing: "Working...",
  complete: "Complete",
  error: "Error",
  waiting_user: "Waiting...",
};

interface StatusBarProps {
  onStop: () => void;
  onClear: () => void;
  onToggleFileTree: () => void;
}

export default function StatusBar({ onStop, onClear, onToggleFileTree }: StatusBarProps) {
  const status = useAgentStore((s) => s.status);
  const connected = useAgentStore((s) => s.connected);

  const isBusy = status === "thinking" || status === "executing";

  return (
    <div
      className="flex items-center gap-1 px-2 py-1 border-t flex-shrink-0"
      style={{
        borderColor: "var(--border-color, rgba(255,255,255,0.1))",
        backgroundColor: "var(--bg-header, #2a2e32)",
        height: "2.25rem",
      }}
    >
      {/* Connection status — single indicator with dot + label */}
      <div
        className="flex items-center gap-1.5 px-2"
        title={connected ? "Agent connected" : "Agent disconnected"}
      >
        <div
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{
            backgroundColor: connected ? STATUS_COLOR[status] : "#E24B4A",
            animation: isBusy ? "pulse 1s ease-in-out infinite" : "none",
            opacity: connected ? 1 : 0.4,
          }}
        />
        <span
          className="text-xs"
          style={{ color: "var(--text-disabled, #7f8c8d)" }}
        >
          {connected ? STATUS_LABEL[status] : "Disconnected"}
        </span>
      </div>

      {/* Separator */}
      <div
        className="w-px h-4 mx-1"
        style={{ backgroundColor: "var(--border-color, rgba(255,255,255,0.1))" }}
      />

      {/* Spacer */}
      <div className="flex-1" />

      {/* Action buttons — right-aligned with consistent sizing */}
      <div className="flex items-center gap-0.5">
        <button
          onClick={onStop}
          disabled={!isBusy}
          className="p-1.5 rounded transition-colors disabled:opacity-20 hover:bg-white/5"
          style={{ color: isBusy ? "#E24B4A" : "var(--text-disabled)" }}
          title="Stop Task"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="1" />
          </svg>
        </button>

        <button
          onClick={onClear}
          className="p-1.5 rounded transition-colors hover:bg-white/5"
          style={{ color: "var(--text-secondary)" }}
          title="Clear Chat"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>

        <button
          className="p-1.5 rounded transition-colors hover:bg-white/5"
          style={{ color: "var(--text-secondary)" }}
          title="Terminal"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="4 17 10 11 4 5" />
            <line x1="12" y1="19" x2="20" y2="19" />
          </svg>
        </button>

        <button
          onClick={onToggleFileTree}
          className="p-1.5 rounded transition-colors hover:bg-white/5"
          style={{ color: "var(--text-secondary)" }}
          title="Context Files"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
