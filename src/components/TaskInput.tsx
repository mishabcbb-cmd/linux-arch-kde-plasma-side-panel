/**
 * src/components/TaskInput.tsx — Multi-line task input.
 *
 * Layout reference: ai_messenger_layout_v2.html
 * textarea + send button side by side, no resize handle.
 * Send button always green (#1D9E75).
 */

import { useState, useRef, type KeyboardEvent } from "react";
import { useAgentStore } from "../store/agentStore";

interface TaskInputProps {
  onSendTask: (task: string) => void;
}

export default function TaskInput({ onSendTask }: TaskInputProps) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const setFileTreeOpen = useAgentStore((s) => s.setFileTreeOpen);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSendTask(trimmed);
    setText("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.key === "Enter" || e.key === "NumpadEnter") && e.ctrlKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasText = text.trim().length > 0;

  return (
    <div className="input-area">
      <div className="input-row">
        <textarea
          ref={inputRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe your task… (Ctrl+Enter to send)"
          rows={2}
        />
        <button
          onClick={handleSend}
          disabled={!hasText}
          className="send-btn"
          aria-label="Send"
          title="Send (Ctrl+Enter)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
      <div className="input-actions">
        <button onClick={() => setFileTreeOpen(true)} className="input-action-btn" title="Attach files">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
          </svg>
          <span>Files</span>
        </button>
      </div>
    </div>
  );
}
