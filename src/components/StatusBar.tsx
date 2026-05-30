/**
 * src/components/StatusBar.tsx — Bottom toolbar.
 *
 * Layout reference: ai_messenger_layout_v2.html
 * Action buttons left, iteration status right.
 */

import { useAgentStore } from "../store/agentStore";

interface StatusBarProps {
  onStop: () => void;
  onClear: () => void;
  onToggleFileTree: () => void;
}

export default function StatusBar({ onStop, onClear, onToggleFileTree }: StatusBarProps) {
  const status = useAgentStore((s) => s.status);
  const connected = useAgentStore((s) => s.connected);
  const messages = useAgentStore((s) => s.messages);
  const isBusy = status === "thinking" || status === "executing";

  // Count tool calls and iterations from messages
  const toolCalls = messages.filter((m) => m.type === "tool_call" || m.type === "tool_result").length;
  const iterations = messages.filter((m) => m.type === "tool_call" && m.iteration).map((m) => m.iteration);
  const maxIteration = iterations.length > 0 ? Math.max(...iterations.map(Number)) : 0;

  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <button
          onClick={onStop}
          disabled={!isBusy}
          className="tool-btn"
          aria-label="Stop"
          title="Stop"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="6" width="12" height="12" rx="1" />
          </svg>
        </button>
        <button onClick={onClear} className="tool-btn" aria-label="Clear" title="Clear">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
        <button className="tool-btn" aria-label="Terminal" title="Terminal">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="4 17 10 11 4 5" />
            <line x1="12" y1="19" x2="20" y2="19" />
          </svg>
        </button>
        <button onClick={onToggleFileTree} className="tool-btn" aria-label="Files" title="Files">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
        </button>
      </div>
      <div className="status-bar">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="4" y="4" width="16" height="16" rx="2" ry="2" />
          <rect x="9" y="9" width="6" height="6" />
          <line x1="9" y1="1" x2="9" y2="4" />
          <line x1="15" y1="1" x2="15" y2="4" />
          <line x1="9" y1="20" x2="9" y2="23" />
          <line x1="15" y1="20" x2="15" y2="23" />
          <line x1="20" y1="9" x2="23" y2="9" />
          <line x1="20" y1="14" x2="23" y2="14" />
          <line x1="1" y1="9" x2="4" y2="9" />
          <line x1="1" y1="14" x2="4" y2="14" />
        </svg>
        <span>
          {connected
            ? isBusy
              ? `iteration ${maxIteration || 1} · ${toolCalls} tool calls`
              : "ready"
            : "disconnected"}
        </span>
      </div>
    </div>
  );
}
