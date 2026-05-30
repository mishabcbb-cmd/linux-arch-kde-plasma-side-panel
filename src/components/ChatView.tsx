/**
 * src/components/ChatView.tsx — Scrollable streaming chat log.
 *
 * Layout reference: ai_messenger_layout_v2.html
 * - User/Agent messages: aligned bubbles
 * - Tool calls: inline color-coded chips (amber=running, teal=done, red=error)
 * - Reasoning: collapsible block with brain icon, dots, chevron
 * - Thinking: animated dots indicator
 */

import { useEffect, useRef, useState } from "react";
import { useAgentStore } from "../store/agentStore";
import type { MessageType } from "../types";

interface ChatViewProps {
  onProvideUserResponse: (response: string) => void;
  onStop: () => void;
}

export default function ChatView({ onProvideUserResponse, onStop }: ChatViewProps) {
  const messages = useAgentStore((s) => s.messages);
  const status = useAgentStore((s) => s.status);
  const scrollRef = useRef<HTMLDivElement>(null);
  const isBusy = status === "thinking" || status === "executing";
  const [expandedReasoning, setExpandedReasoning] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, expandedReasoning]);

  const toggleReasoning = (id: string) => {
    setExpandedReasoning((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const isUserOrAgent = (type: MessageType) => type === "user" || type === "agent";
  const isToolType = (type: MessageType) => type === "tool_call" || type === "tool_result";

  return (
    <div ref={scrollRef} className="chat">
      {messages.length === 0 && !isBusy && (
        <div className="chat-empty">
          <div className="chat-empty-icon">🤖</div>
          <div className="chat-empty-text">Describe a task below to get started</div>
        </div>
      )}

      {messages.map((msg) => {
        // ── User / Agent bubbles ──
        if (isUserOrAgent(msg.type)) {
          return (
            <div key={msg.id} className={`msg ${msg.type}`}>
              <span className="msg-label">{msg.type === "user" ? "You" : "Agent"}</span>
              <div className="msg-bubble">{msg.content}</div>
            </div>
          );
        }

        // ── Tool call / result chips ──
        if (isToolType(msg.type)) {
          const isRunning = msg.type === "tool_call";
          const isDone = msg.type === "tool_result" && msg.success !== false;
          const isError = msg.type === "tool_result" && msg.success === false;
          let toolClass = "msg-tool";
          if (isRunning) toolClass += " running";
          if (isDone) toolClass += " done";
          if (isError) toolClass += " error";

          return (
            <div key={msg.id} className="msg agent">
              <div className={toolClass}>
                {isDone ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : isRunning ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="spin">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                  </svg>
                ) : (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                  </svg>
                )}
                <span>{msg.toolName} — {msg.content.length > 80 ? msg.content.substring(0, 80) + "…" : msg.content}</span>
              </div>
            </div>
          );
        }

        // ── Reasoning (thought messages become collapsible) ──
        if (msg.type === "thought") {
          const isOpen = expandedReasoning[msg.id] || false;
          return (
            <div key={msg.id} className="reasoning">
              <button
                className={`reasoning-toggle ${isOpen ? "open" : ""}`}
                onClick={() => toggleReasoning(msg.id)}
                aria-expanded={isOpen}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z" />
                  <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z" />
                </svg>
                <span>thinking</span>
                {!isOpen && (
                  <div className="dot-anim">
                    <span /><span /><span />
                  </div>
                )}
                <svg
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="chevron"
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              <div className={`reasoning-body ${isOpen ? "visible" : ""}`}>
                {msg.content}
              </div>
            </div>
          );
        }

        // ── Question with options ──
        if (msg.type === "question" && msg.options && msg.options.length > 0) {
          return (
            <div key={msg.id} className="msg agent">
              <span className="msg-label">Agent</span>
              <div className="msg-bubble">{msg.content}</div>
              <div className="msg-options">
                {msg.options.map((opt) => (
                  <button key={opt} onClick={() => onProvideUserResponse(opt)} className="msg-option-btn">
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          );
        }

        // ── Error ──
        if (msg.type === "error") {
          return (
            <div key={msg.id} className="msg agent">
              <div className="msg-tool error">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                </svg>
                <span>{msg.content}</span>
              </div>
            </div>
          );
        }

        // ── Default: task_complete etc ──
        return (
          <div key={msg.id} className="msg agent">
            <span className="msg-label">Agent</span>
            <div className="msg-bubble">{msg.content}</div>
          </div>
        );
      })}

      {/* Thinking indicator when busy and no messages yet */}
      {isBusy && messages.length === 0 && (
        <div className="thinking">
          <div className="dot-anim">
            <span /><span /><span />
          </div>
          <span>{status === "thinking" ? "thinking" : "working"}</span>
          <button onClick={onStop} className="thinking-stop">Stop</button>
        </div>
      )}
    </div>
  );
}
