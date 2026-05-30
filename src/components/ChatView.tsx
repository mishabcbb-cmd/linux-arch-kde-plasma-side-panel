/**
 * src/components/ChatView.tsx — Scrollable streaming chat log.
 *
 * React equivalent of ChatView.qml.
 * Color-coded by message type, matching the QML spec:
 *   thought       → default text
 *   tool_call     → amber #EF9F27
 *   tool_result   → teal #1D9E75
 *   error         → red #E24B4A
 *   task_complete → green #639922
 *   question      → blue #3DAEE9
 *
 * Streaming pattern: tokens append to the last message as they arrive,
 * matching the QML end4 pattern from SidePanelWindow.qml.
 */

import { useEffect, useRef } from "react";
import { useAgentStore } from "../store/agentStore";
import type { MessageType } from "../types";

// ── Color map (matches QML getColor()) ──
const COLOR_MAP: Record<MessageType, string> = {
  tool_call: "#EF9F27",
  tool_result: "#1D9E75",
  error: "#E24B4A",
  task_complete: "#639922",
  question: "#3DAEE9",
  thought: "var(--text-primary, #eff1f5)",
};

// ── Background tint map (matches QML delegate background) ──
const BG_MAP: Record<MessageType, string> = {
  tool_call: "rgba(239, 159, 39, 0.06)",
  tool_result: "rgba(29, 158, 117, 0.06)",
  error: "rgba(226, 75, 74, 0.06)",
  task_complete: "rgba(99, 153, 34, 0.08)",
  question: "rgba(61, 174, 233, 0.06)",
  thought: "transparent",
};

interface ChatViewProps {
  onProvideUserResponse: (response: string) => void;
  onStop: () => void;
}

export default function ChatView({ onProvideUserResponse, onStop }: ChatViewProps) {
  const messages = useAgentStore((s) => s.messages);
  const status = useAgentStore((s) => s.status);
  const scrollRef = useRef<HTMLDivElement>(null);

  const isBusy = status === "thinking" || status === "executing";

  // Auto-scroll to bottom on new messages (matches QML positionViewAtEnd)
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto px-3 py-2 space-y-1"
      style={{
        borderBottom: "1px solid var(--border-color, rgba(255,255,255,0.06))",
      }}
    >
      {/* Empty state — only when no messages AND not busy */}
      {messages.length === 0 && !isBusy && (
        <div className="flex items-center justify-center h-full">
          <div className="text-center opacity-40">
            <div className="text-3xl mb-3">🤖</div>
            <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
              AI Agent Panel
            </div>
            <div className="text-xs mt-1" style={{ color: "var(--text-disabled)" }}>
              Describe a task below to get started
            </div>
          </div>
        </div>
      )}

      {/* Busy indicator — shown when no messages yet but agent is working */}
      {messages.length === 0 && isBusy && (
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <div className="flex items-center gap-2 justify-center mb-2">
              <div
                className="w-2.5 h-2.5 rounded-full"
                style={{
                  backgroundColor: status === "thinking" ? "#3DAEE9" : "#EF9F27",
                  animation: "pulse 1s ease-in-out infinite",
                }}
              />
              <span className="text-sm" style={{ color: "var(--text-primary)" }}>
                {status === "thinking" ? "Thinking..." : "Working..."}
              </span>
            </div>
            <button
              onClick={onStop}
              className="px-3 py-1 text-xs rounded-md border hover:opacity-80 transition-colors"
              style={{
                borderColor: "rgba(226, 75, 74, 0.4)",
                color: "#E24B4A",
                backgroundColor: "rgba(226, 75, 74, 0.08)",
              }}
            >
              Stop
            </button>
          </div>
        </div>
      )}

      {/* Messages */}
      {messages.map((msg) => (
        <div
          key={msg.id}
          className="rounded-md p-2 flex gap-2 items-start"
          style={{ backgroundColor: BG_MAP[msg.type] }}
        >
          {/* Icon */}
          <span
            className="flex-shrink-0 mt-0.5 text-xs"
            style={{ color: COLOR_MAP[msg.type] }}
          >
            <MessageIcon type={msg.type} />
          </span>

          <div className="flex-1 min-w-0">
            {/* Tool name label */}
            {msg.toolName && (
              <div
                className="text-xs font-bold mb-0.5"
                style={{ color: COLOR_MAP[msg.type] }}
              >
                {msg.toolName}
              </div>
            )}

            {/* Content */}
            <div
              className="text-sm whitespace-pre-wrap break-words"
              style={{ color: COLOR_MAP[msg.type] }}
            >
              {msg.content}
            </div>

            {/* Question options (for ask_user) */}
            {msg.type === "question" && msg.options && msg.options.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {msg.options.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => onProvideUserResponse(opt)}
                    className="px-3 py-1 text-xs rounded-md border transition-colors hover:opacity-80"
                    style={{
                      borderColor: COLOR_MAP.question,
                      color: COLOR_MAP.question,
                      backgroundColor: "rgba(61, 174, 233, 0.1)",
                    }}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Streaming cursor — shown when busy and last message is a thought */}
      {isBusy && messages.length > 0 && messages[messages.length - 1].type === "thought" && (
        <div className="flex items-center gap-1 px-2 py-1">
          <div
            className="w-1.5 h-4 rounded-sm"
            style={{
              backgroundColor: "var(--accent-color, #3DAEE9)",
              animation: "pulse 0.8s ease-in-out infinite",
            }}
          />
        </div>
      )}
    </div>
  );
}

// ── Simple SVG icon component (replacing Kirigami.Icon) ──
function MessageIcon({ type }: { type: MessageType }) {
  const color = COLOR_MAP[type];
  const size = 14;

  switch (type) {
    case "thought":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
        </svg>
      );
    case "tool_call":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
        </svg>
      );
    case "tool_result":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
        </svg>
      );
    case "error":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
        </svg>
      );
    case "task_complete":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" /><path d="m9 12 2 2 4-4" />
        </svg>
      );
    case "question":
      return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      );
    default:
      return null;
  }
}
